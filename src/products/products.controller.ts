import {
  Controller,
  Get,
  Param,
  Query,
  Post,
  Put,
  Delete,
  Body,
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { ProductsService } from './products.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';
import { Roles } from '../auth/roles.decorator';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import type {
  CreateProductDto,
  UpdateProductDto,
  ProductQueryDto,
} from './schemas/product.schema';
import { CreateProductSchema, UpdateProductSchema, ProductQuerySchema } from './schemas/product.schema';

@ApiTags(COLLECTION_NAMES.PRODUCTS)
@Controller(COLLECTION_NAMES.PRODUCTS)
export class ProductsController extends BaseController {
  constructor(
    private readonly productsService: ProductsService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get all products with optional filtering
  @Public()
  @Get()
  @UsePipes(new ZodValidationPipe(ProductQuerySchema))
  async findAll(@Query() query: ProductQueryDto) {
    this.logInfo('Fetching all products');
    const products = await this.productsService.findAll(query);
    return this.formatResponse(products, 'Products retrieved successfully');
  }

  // Get a specific product by ID
  @Public()
  @Get(':id')
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching product with ID: ${id}`);
    const product = await this.productsService.findOne(id);
    return this.formatResponse(product, 'Product retrieved successfully');
  }

  // Create a new product
  @Post()
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(CreateProductSchema))
  async create(@Body() createProductDto: CreateProductDto) {
    this.logInfo('Creating new product');
    const product = await this.productsService.create(createProductDto);
    return this.formatResponse(product, 'Product created successfully');
  }

  // Update a product
  @Put(':id')
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(UpdateProductSchema))
  async update(
    @Param('id') id: string,
    @Body() updateProductDto: UpdateProductDto,
  ) {
    this.logInfo(`Updating product with ID: ${id}`);
    const product = await this.productsService.update(id, updateProductDto);
    return this.formatResponse(product, 'Product updated successfully');
  }

  // Delete a product
  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    this.logInfo(`Deleting product with ID: ${id}`);
    const result = await this.productsService.remove(id);
    return this.formatResponse(result, 'Product deleted successfully');
  }
}