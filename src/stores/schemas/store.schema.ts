import { z } from 'zod';
import { InventorySchema } from '../../inventory/schemas/inventory.schema';

export const LocationSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
});

export const StoreSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  address: z.string().min(1),
  phone: z.string().optional(),
  email: z.string().email().optional(),
  location: LocationSchema,
  isActive: z.boolean().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
  inventory: z.array(InventorySchema).optional(),
});

export const CreateStoreSchema = StoreSchema.omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});

export const UpdateStoreSchema = StoreSchema.partial().omit({ 
  id: true, 
  createdAt: true 
});

export const NearbyStoresQuerySchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  radius: z.number().min(1).max(100).optional(), // in kilometers, default 10km
  limit: z.number().min(1).max(100).optional(), // default 10
  includeInventory: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
});

export const StoreQuerySchema = z.object({
  includeInventory: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
}).partial();

export type Store = z.infer<typeof StoreSchema>;
export type CreateStoreDto = z.infer<typeof CreateStoreSchema>;
export type UpdateStoreDto = z.infer<typeof UpdateStoreSchema>;
export type Location = z.infer<typeof LocationSchema>;
export type NearbyStoresQuery = z.infer<typeof NearbyStoresQuerySchema>;
export type StoreQuery = z.infer<typeof StoreQuerySchema>;