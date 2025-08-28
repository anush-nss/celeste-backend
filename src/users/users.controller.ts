import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Param,
  Body,
  Query,
  HttpStatus,
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';
import { Roles } from '../auth/roles.decorator';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import type {
  CreateUserDto,
  UpdateUserDto,
  AddToWishlistDto,
  AddToCartDto,
  UpdateCartItemDto,
} from './schemas/user.schema';
import { CreateUserSchema, UpdateUserSchema, AddToWishlistSchema, AddToCartSchema, UpdateCartItemSchema } from './schemas/user.schema';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';

@ApiTags(COLLECTION_NAMES.USERS)
@Controller(COLLECTION_NAMES.USERS)
export class UsersController extends BaseController {
  constructor(
    private readonly usersService: UsersService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get user profile
  @Get(':id')
  @Roles(USER_ROLES.CUSTOMER)
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching user with ID: ${id}`);
    const user = this.usersService.findOne(id);
    return this.formatResponse(user, 'User retrieved successfully');
  }

  // Create a new user
  @Public()
  @Post()
  async create(@Body(new ZodValidationPipe(CreateUserSchema)) createUserDto: CreateUserDto) {
    this.logInfo('Creating new user');
    const user = this.usersService.create(createUserDto);
    return this.formatResponse(user, 'User created successfully');
  }

  // Update user profile
  @Put(':id')
  @Roles(USER_ROLES.CUSTOMER)
  async update(
    @Param('id') id: string,
    @Body(new ZodValidationPipe(UpdateUserSchema)) updateUserDto: UpdateUserDto,
  ) {
    this.logInfo(`Updating user with ID: ${id}`);
    const user = this.usersService.update(id, updateUserDto);
    return this.formatResponse(user, 'User updated successfully');
  }

  // Delete user
  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    this.logInfo(`Deleting user with ID: ${id}`);
    const result = this.usersService.remove(id);
    return this.formatResponse(result, 'User deleted successfully');
  }

  // Add to wishlist
  @Post(':id/wishlist')
  @Roles(USER_ROLES.CUSTOMER)
  @UsePipes(new ZodValidationPipe(AddToWishlistSchema))
  async addToWishlist(
    @Param('id') id: string,
    @Body() body: AddToWishlistDto,
  ) {
    this.logInfo(`Adding product to wishlist for user ID: ${id}`);
    const result = this.usersService.addToWishlist(id, body.productId);
    return this.formatResponse(result, 'Product added to wishlist');
  }

  // Remove from wishlist
  @Delete(':id/wishlist/:productId')
  @Roles(USER_ROLES.CUSTOMER)
  async removeFromWishlist(
    @Param('id') id: string,
    @Param('productId') productId: string,
  ) {
    this.logInfo(`Removing product from wishlist for user ID: ${id}`);
    const result = this.usersService.removeFromWishlist(id, productId);
    return this.formatResponse(result, 'Product removed from wishlist');
  }

  // Add to cart
  @Post(':id/cart')
  @Roles(USER_ROLES.CUSTOMER)
  @UsePipes(new ZodValidationPipe(AddToCartSchema))
  async addToCart(
    @Param('id') id: string,
    @Body() body: AddToCartDto,
  ) {
    this.logInfo(`Adding item to cart for user ID: ${id}`);
    const result = this.usersService.addToCart(id, body);
    return this.formatResponse(result, 'Item added to cart');
  }

  // Update cart item
  @Put(':id/cart/:productId')
  @Roles(USER_ROLES.CUSTOMER)
  @UsePipes(new ZodValidationPipe(UpdateCartItemSchema))
  async updateCartItem(
    @Param('id') id: string,
    @Param('productId') productId: string,
    @Body() body: UpdateCartItemDto,
  ) {
    this.logInfo(`Updating cart item for user ID: ${id}`);
    const result = this.usersService.updateCartItem(id, productId, body.quantity);
    return this.formatResponse(result, 'Cart item updated');
  }

  // Remove from cart
  @Delete(':id/cart/:productId')
  @Roles(USER_ROLES.CUSTOMER)
  async removeFromCart(
    @Param('id') id: string,
    @Param('productId') productId: string,
  ) {
    this.logInfo(`Removing item from cart for user ID: ${id}`);
    const result = this.usersService.removeFromCart(id, productId);
    return this.formatResponse(result, 'Item removed from cart');
  }
}