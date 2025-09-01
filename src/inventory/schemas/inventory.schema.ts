import { z } from 'zod';

export const InventorySchema = z.object({
  id: z.string().optional(),
  productId: z.string(),
  storeId: z.string(),
  stock: z.number().int().nonnegative(),
  lastUpdated: z.date().optional(),
});

export const CreateInventorySchema = InventorySchema.omit({ id: true, lastUpdated: true });
export const UpdateInventorySchema = InventorySchema.partial().omit({ id: true, productId: true, storeId: true });

export type Inventory = z.infer<typeof InventorySchema>;
export type CreateInventoryDto = z.infer<typeof CreateInventorySchema>;
export type UpdateInventoryDto = z.infer<typeof UpdateInventorySchema>;