from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import Annotated, List, Optional
from src.models.product_models import ProductSchema, CreateProductSchema, UpdateProductSchema, ProductQuerySchema
from src.models.pricing_models import PriceCalculationResponse
from src.models.token_models import DecodedToken
from src.services.product_service import ProductService
from src.services.pricing_service import PricingService
from src.auth.dependencies import RoleChecker, get_current_user
from src.shared.constants import UserRole, CustomerTier
from src.core.exceptions import ResourceNotFoundException
from src.core.responses import success_response

products_router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()
pricing_service = PricingService()

@products_router.get("/", summary="Get all products", response_model=List[ProductSchema])
async def get_all_products(
    limit: Optional[int] = Query(None, description="Limit the number of products returned"),
    offset: Optional[int] = Query(None, description="Offset for pagination"),
    includeDiscounts: Optional[bool] = Query(None, description="Include discounts for each product"),
    includeInventory: Optional[bool] = Query(None, description="Include inventory for each product"),
    categoryId: Optional[str] = Query(None, description="Filter by category ID"),
    minPrice: Optional[float] = Query(None, description="Filter by minimum price"),
    maxPrice: Optional[float] = Query(None, description="Filter by maximum price"),
    isFeatured: Optional[bool] = Query(None, description="Filter by featured products"),
    tier: Optional[str] = Query(None, description="Customer tier for pricing (bronze, silver, gold, platinum)"),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
):
    query_params = ProductQuerySchema(
        limit=limit,
        offset=offset,
        includeDiscounts=includeDiscounts,
        categoryId=categoryId,
        minPrice=minPrice,
        maxPrice=maxPrice,
        isFeatured=isFeatured
    )
    products = await product_service.get_all_products(query_params)
    
    # If tier is specified, calculate tier-based pricing for each product
    if tier:
        try:
            customer_tier = CustomerTier(tier)
            enhanced_products = []
            
            for product in products:
                product_dict = product.model_dump(mode='json')
                
                # Only calculate pricing if product has required fields
                if product.id and quantity:
                    # Calculate tier-based price
                    calculation = await pricing_service.calculate_price(
                        product.id, customer_tier, quantity
                    )
                    
                    # Add pricing information to product
                    product_dict['tier_pricing'] = {
                        'base_price': calculation.base_price,
                        'tier_price': calculation.final_price,
                        'discount_applied': calculation.discount_applied,
                        'discount_percentage': calculation.discount_percentage,
                        'customer_tier': calculation.customer_tier,
                        'applied_price_lists': calculation.applied_price_lists
                    }
                
                enhanced_products.append(product_dict)
            
            return success_response(enhanced_products)
            
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid tier: {tier}")
    
    return success_response([p.model_dump(mode='json') for p in products])

@products_router.get("/{id}", summary="Get a product by ID")
async def get_product_by_id(
    id: str,
    includeDiscounts: Optional[bool] = Query(None, description="Include discounts for the product"),
    includeInventory: Optional[bool] = Query(None, description="Include inventory for the product"),
    tier: Optional[str] = Query(None, description="Customer tier for pricing (bronze, silver, gold, platinum)"),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
):
    product = await product_service.get_product_by_id(id)
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    
    product_dict = product.model_dump(mode='json')
    
    # If tier is specified, calculate tier-based pricing
    if tier:
        try:
            customer_tier = CustomerTier(tier)
            
            # Only calculate pricing if product has required fields
            if product.id and quantity:
                # Calculate tier-based price
                calculation = await pricing_service.calculate_price(
                    product.id, customer_tier, quantity
                )
                
                # Add pricing information to product
                product_dict['tier_pricing'] = {
                    'base_price': calculation.base_price,
                    'tier_price': calculation.final_price,
                    'discount_applied': calculation.discount_applied,
                    'discount_percentage': calculation.discount_percentage,
                    'customer_tier': calculation.customer_tier,
                    'applied_price_lists': calculation.applied_price_lists,
                    'quantity': calculation.quantity
                }
            
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid tier: {tier}")
    
    # TODO: Implement logic to include discounts and inventory if requested
    return success_response(product_dict)

@products_router.post("/", summary="Create a new product", response_model=ProductSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_product(product_data: CreateProductSchema):
    new_product = await product_service.create_product(product_data)
    return success_response(new_product.model_dump(mode='json'), status_code=status.HTTP_201_CREATED)

@products_router.put("/{id}", summary="Update a product", response_model=ProductSchema, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_product(id: str, product_data: UpdateProductSchema):
    updated_product = await product_service.update_product(id, product_data)
    if not updated_product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response(updated_product.model_dump(mode='json'))

@products_router.delete("/{id}", summary="Delete a product", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_product(id: str):
    if not await product_service.delete_product(id):
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response({"id": id, "message": "Product deleted successfully"})

# Authenticated user endpoints with automatic tier pricing
@products_router.get("/my-pricing", summary="Get all products with current user's tier pricing")
async def get_products_with_my_pricing(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    limit: Optional[int] = Query(None, description="Limit the number of products returned"),
    offset: Optional[int] = Query(None, description="Offset for pagination"),
    categoryId: Optional[str] = Query(None, description="Filter by category ID"),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
):
    """
    Get all products with pricing based on the current user's tier.
    Requires authentication.
    """
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
    
    # TODO: Get user's actual tier from user service
    # For now, we'll use a default tier
    customer_tier = CustomerTier.BRONZE  # This should be fetched from user service
    
    query_params = ProductQuerySchema(
        limit=limit,
        offset=offset,
        categoryId=categoryId
    )
    products = await product_service.get_all_products(query_params)
    
    enhanced_products = []
    for product in products:
        product_dict = product.model_dump(mode='json')
        
        # Only calculate pricing if product has required fields
        if product.id and quantity:
            # Calculate tier-based price
            calculation = await pricing_service.calculate_price(
                product.id, customer_tier, quantity
            )
            
            # Add pricing information to product
            product_dict['tier_pricing'] = {
                'base_price': calculation.base_price,
                'tier_price': calculation.final_price,
                'discount_applied': calculation.discount_applied,
                'discount_percentage': calculation.discount_percentage,
                'customer_tier': calculation.customer_tier,
                'applied_price_lists': calculation.applied_price_lists
            }
        
        enhanced_products.append(product_dict)
    
    return success_response(enhanced_products)

@products_router.get("/my-pricing/{id}", summary="Get product with current user's tier pricing")
async def get_product_with_my_pricing(
    id: str,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
):
    """
    Get a specific product with pricing based on the current user's tier.
    Requires authentication.
    """
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
    
    product = await product_service.get_product_by_id(id)
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    
    # TODO: Get user's actual tier from user service
    customer_tier = CustomerTier.BRONZE  # This should be fetched from user service
    
    product_dict = product.model_dump(mode='json')
    
    # Only calculate pricing if product has required fields
    if product.id and quantity:
        # Calculate tier-based price
        calculation = await pricing_service.calculate_price(
            product.id, customer_tier, quantity
        )
        
        # Add pricing information to product
        product_dict['tier_pricing'] = {
            'base_price': calculation.base_price,
            'tier_price': calculation.final_price,
            'discount_applied': calculation.discount_applied,
            'discount_percentage': calculation.discount_percentage,
            'customer_tier': calculation.customer_tier,
            'applied_price_lists': calculation.applied_price_lists,
            'quantity': calculation.quantity
        }
    
    return success_response(product_dict)