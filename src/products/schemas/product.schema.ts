import { z } from 'zod';
import { DiscountSchema } from '../../discounts/schemas/discount.schema';
import { InventorySchema } from '../../inventory/schemas/inventory.schema';

export const ProductSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  price: z.number().nonnegative(),
  unit: z.string(),
  categoryId: z.string(),
  imageUrl: z.string().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
  discounts: z.array(DiscountSchema).optional(),
  inventory: z.array(InventorySchema).optional(),
});

export const CreateProductSchema = ProductSchema.omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true,
});
export const UpdateProductSchema = ProductSchema.partial().omit({ 
  id: true, 
  createdAt: true,
});

// New schema for product query parameters
export const ProductQuerySchema = z.object({
  limit: z.preprocess(
    (a) => parseInt(z.string().parse(a), 10),
    z.number().int().positive().optional(),
  ),
  offset: z.preprocess(
    (a) => parseInt(z.string().parse(a), 10),
    z.number().int().nonnegative().optional(),
  ),
  includeDiscounts: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
  includeInventory: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
  categoryId: z.string().optional(),
}).partial(); // Make all query parameters optional

export type Product = z.infer<typeof ProductSchema>;
export type CreateProductDto = z.infer<typeof CreateProductSchema>;
export type UpdateProductDto = z.infer<typeof UpdateProductSchema>;
export type ProductQueryDto = z.infer<typeof ProductQuerySchema>;