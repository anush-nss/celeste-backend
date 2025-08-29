import { Injectable, NotFoundException } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { User, CreateUserDto, UpdateUserDto, type AddToCartDto, type CartItem } from './schemas/user.schema';
import * as admin from 'firebase-admin';

@Injectable()
export class UsersService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestoreService: FirestoreService,
  ) {}

  // Find a user by ID
  async findOne(id: string): Promise<User> {
    this.logger.log(`Finding user with ID: ${id}`, UsersService.name);
    const user = await this.firestoreService.getById(COLLECTION_NAMES.USERS, id);
    if (!user) {
      throw new NotFoundException(`User with ID ${id} not found`);
    }
    return user as User;
  }

  // Create a new user
  async create(createUserDto: CreateUserDto): Promise<User> {
    this.logger.log(`Creating new user`, UsersService.name);
    const newUser = await this.firestoreService.create(COLLECTION_NAMES.USERS, createUserDto);
    return newUser as User;
  }

  // Update a user
  async update(id: string, updateUserDto: UpdateUserDto): Promise<User> {
    this.logger.log(`Updating user with ID: ${id}`, UsersService.name);
    const existingUser = await this.firestoreService.getById(COLLECTION_NAMES.USERS, id);
    if (!existingUser) {
      throw new NotFoundException(`User with ID ${id} not found`);
    }
    const updatedUser = await this.firestoreService.update(COLLECTION_NAMES.USERS, id, updateUserDto);
    return updatedUser as User;
  }

  // Delete a user
  async remove(id: string): Promise<{ id: string }> {
    this.logger.log(`Deleting user with ID: ${id}`, UsersService.name);
    const existingUser = await this.firestoreService.getById(COLLECTION_NAMES.USERS, id);
    if (!existingUser) {
      throw new NotFoundException(`User with ID ${id} not found`);
    }
    await this.firestoreService.delete(COLLECTION_NAMES.USERS, id);
    return { id };
  }

  // Add to wishlist
  async addToWishlist(userId: string, productId: string): Promise<{ userId: string, productId: string }> {
    this.logger.log(`Adding product ${productId} to user ${userId} wishlist`, UsersService.name);
    await this.firestoreService.update(COLLECTION_NAMES.USERS, userId, {
      wishlist: admin.firestore.FieldValue.arrayUnion(productId),
    });
    return { userId, productId };
  }

  // Remove from wishlist
  async removeFromWishlist(userId: string, productId: string): Promise<{ userId: string, productId: string }> {
    this.logger.log(`Removing product ${productId} from user ${userId} wishlist`, UsersService.name);
    await this.firestoreService.update(COLLECTION_NAMES.USERS, userId, {
      wishlist: admin.firestore.FieldValue.arrayRemove(productId),
    });
    return { userId, productId };
  }

  // Add to cart
  async addToCart(userId: string, cartItem: AddToCartDto): Promise<CartItem> {
    this.logger.log(`Adding item to user ${userId} cart`, UsersService.name);
    const user = await this.findOne(userId);
    const existingCartItem = user.cart?.find(item => item.productId === cartItem.productId);

    if (existingCartItem) {
      // If item exists, update quantity
      const newQuantity = existingCartItem.quantity + cartItem.quantity;
      return this.updateCartItem(userId, cartItem.productId, newQuantity);
    } else {
      // If item does not exist, add it to cart
      const newCartItem = { ...cartItem, addedAt: new Date() };
      await this.firestoreService.update(COLLECTION_NAMES.USERS, userId, {
        cart: admin.firestore.FieldValue.arrayUnion(newCartItem),
      });
      return newCartItem;
    }
  }

  // Update cart item
  async updateCartItem(userId: string, productId: string, quantity: number): Promise<CartItem> {
    this.logger.log(`Updating cart item for user ${userId}`, UsersService.name);
    const user = await this.findOne(userId);
    const cart = user.cart || [];
    const itemIndex = cart.findIndex(item => item.productId === productId);

    if (itemIndex > -1) {
      cart[itemIndex].quantity = quantity;
      cart[itemIndex].addedAt = new Date();
      await this.firestoreService.update(COLLECTION_NAMES.USERS, userId, { cart });
      return cart[itemIndex];
    } else {
      throw new NotFoundException(`Product with ID ${productId} not in cart`);
    }
  }

  // Remove from cart
  async removeFromCart(userId: string, productId: string): Promise<{ userId: string, productId: string }> {
    this.logger.log(`Removing item from user ${userId} cart`, UsersService.name);
    const user = await this.findOne(userId);
    const cart = user.cart || [];
    const updatedCart = cart.filter(item => item.productId !== productId);

    await this.firestoreService.update(COLLECTION_NAMES.USERS, userId, { cart: updatedCart });
    return { userId, productId };
  }
}
