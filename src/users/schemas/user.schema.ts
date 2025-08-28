import { z } from 'zod';

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
  role: z.enum(['customer', 'admin']),
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

export type User = z.infer<typeof UserSchema>;
export type CreateUserDto = z.infer<typeof CreateUserSchema>;
export type UpdateUserDto = z.infer<typeof UpdateUserSchema>;
export type CartItem = z.infer<typeof CartItemSchema>;