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
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import { CreateUserSchema, UpdateUserSchema } from './schemas/user.schema';

@ApiTags('users')
@Controller('users')
export class UsersController extends BaseController {
  constructor(
    private readonly usersService: UsersService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get user profile
  @Get(':id')
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching user with ID: ${id}`);
    const user = this.usersService.findOne(id);
    return this.formatResponse(user, 'User retrieved successfully');
  }

  // Create a new user
  @Public()
  @Post()
  async create(@Body(new ZodValidationPipe(CreateUserSchema)) createUserDto: any) {
    this.logInfo('Creating new user');
    const user = this.usersService.create(createUserDto);
    return this.formatResponse(user, 'User created successfully');
  }

  // Update user profile
  @Put(':id')
  async update(
    @Param('id') id: string,
    @Body(new ZodValidationPipe(UpdateUserSchema)) updateUserDto: any,
  ) {
    this.logInfo(`Updating user with ID: ${id}`);
    const user = this.usersService.update(id, updateUserDto);
    return this.formatResponse(user, 'User updated successfully');
  }

  // Delete user
  @Delete(':id')
  async remove(@Param('id') id: string) {
    this.logInfo(`Deleting user with ID: ${id}`);
    const result = this.usersService.remove(id);
    return this.formatResponse(result, 'User deleted successfully');
  }

  // Add to wishlist
  @Post(':id/wishlist')
  async addToWishlist(
    @Param('id') id: string,
    @Body() body: any,
  ) {
    this.logInfo(`Adding product to wishlist for user ID: ${id}`);
    const result = this.usersService.addToWishlist(id, body.productId);
    return this.formatResponse(result, 'Product added to wishlist');
  }

  // Remove from wishlist
  @Delete(':id/wishlist/:productId')
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
  async addToCart(
    @Param('id') id: string,
    @Body() body: any,
  ) {
    this.logInfo(`Adding item to cart for user ID: ${id}`);
    const result = this.usersService.addToCart(id, body);
    return this.formatResponse(result, 'Item added to cart');
  }

  // Update cart item
  @Put(':id/cart/:productId')
  async updateCartItem(
    @Param('id') id: string,
    @Param('productId') productId: string,
    @Body() body: any,
  ) {
    this.logInfo(`Updating cart item for user ID: ${id}`);
    const result = this.usersService.updateCartItem(id, productId, body.quantity);
    return this.formatResponse(result, 'Cart item updated');
  }

  // Remove from cart
  @Delete(':id/cart/:productId')
  async removeFromCart(
    @Param('id') id: string,
    @Param('productId') productId: string,
  ) {
    this.logInfo(`Removing item from cart for user ID: ${id}`);
    const result = this.usersService.removeFromCart(id, productId);
    return this.formatResponse(result, 'Item removed from cart');
  }
}