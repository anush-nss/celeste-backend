import { z } from 'zod';
import { USER_ROLES } from '../../shared/constants';

export const CartItemSchema = z.object({
  productId: z.string(),
  quantity: z.number().int().positive(),
  addedAt: z.date(),
});

export const UserSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  email: z.string().email(),
  phone: z.string().optional(),
  address: z.string().optional(),
  role: z.enum([USER_ROLES.CUSTOMER, USER_ROLES.ADMIN]),
  createdAt: z.date().optional(),
  wishlist: z.array(z.string()).optional(),
  cart: z.array(CartItemSchema).optional(),
});

export const CreateUserSchema = UserSchema.omit({ 
  id: true, 
  createdAt: true, 
  wishlist: true, 
  cart: true 
});

export const UpdateUserSchema = UserSchema.partial().omit({ 
  id: true, 
  createdAt: true 
});

// New schemas for request bodies
export const AddToWishlistSchema = z.object({
  productId: z.string().min(1),
});

export const AddToCartSchema = z.object({
  productId: z.string().min(1),
  quantity: z.number().int().positive(),
});

export const UpdateCartItemSchema = z.object({
  quantity: z.number().int().positive(),
});


export type User = z.infer<typeof UserSchema>;
export type CreateUserDto = z.infer<typeof CreateUserSchema>;
export type UpdateUserDto = z.infer<typeof UpdateUserSchema>;
export type CartItem = z.infer<typeof CartItemSchema>;
export type AddToWishlistDto = z.infer<typeof AddToWishlistSchema>;
export type AddToCartDto = z.infer<typeof AddToCartSchema>;
export type UpdateCartItemDto = z.infer<typeof UpdateCartItemSchema>;