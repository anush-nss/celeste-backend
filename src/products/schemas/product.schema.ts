import { z } from 'zod';

export const ProductSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  price: z.number().nonnegative(),
  stock: z.number().int().nonnegative(),
  unit: z.string(),
  categoryId: z.string(),
  imageUrl: z.string().optional(),
  isFeatured: z.boolean().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});

export const CreateProductSchema = ProductSchema.omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true,
  isFeatured: true
});
export const UpdateProductSchema = ProductSchema.partial().omit({ 
  id: true, 
  createdAt: true,
  isFeatured: true
});

export type Product = z.infer<typeof ProductSchema>;
export type CreateProductDto = z.infer<typeof CreateProductSchema>;
export type UpdateProductDto = z.infer<typeof UpdateProductSchema>;