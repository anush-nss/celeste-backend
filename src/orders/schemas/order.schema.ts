import { z } from 'zod';

export const OrderItemSchema = z.object({
  productId: z.string(),
  name: z.string(),
  price: z.number().nonnegative(),
  quantity: z.number().int().positive(),
});

export const OrderSchema = z.object({
  id: z.string().optional(),
  userId: z.string(),
  items: z.array(OrderItemSchema),
  totalAmount: z.number().nonnegative(),
  discountApplied: z.string().nullable(),
  promotionApplied: z.string().nullable(),
  status: z.enum(['pending', 'processing', 'shipped', 'delivered', 'cancelled']),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});

export const CreateOrderSchema = OrderSchema.omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});
export const UpdateOrderSchema = OrderSchema.partial().omit({ 
  id: true, 
  createdAt: true,
  userId: true,
  items: true,
  totalAmount: true
});

export type Order = z.infer<typeof OrderSchema>;
export type CreateOrderDto = z.infer<typeof CreateOrderSchema>;
export type UpdateOrderDto = z.infer<typeof UpdateOrderSchema>;
export type OrderItem = z.infer<typeof OrderItemSchema>;