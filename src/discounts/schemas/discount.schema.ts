import { z } from 'zod';

export const DiscountSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  type: z.enum(['percentage', 'flat']),
  value: z.number().nonnegative(),
  validFrom: z.date(),
  validTo: z.date(),
  applicableProducts: z.array(z.string()).optional(),
  applicableCategories: z.array(z.string()).optional(),
});

export const CreateDiscountSchema = DiscountSchema.omit({ id: true });
export const UpdateDiscountSchema = DiscountSchema.partial().omit({ id: true });

export type Discount = z.infer<typeof DiscountSchema>;
export type CreateDiscountDto = z.infer<typeof CreateDiscountSchema>;
export type UpdateDiscountDto = z.infer<typeof UpdateDiscountSchema>;