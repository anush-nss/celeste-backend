import { z } from 'zod';
import { DISCOUNT_TYPES } from '../../shared/constants';

export const DiscountSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  type: z.enum([DISCOUNT_TYPES.PERCENTAGE, DISCOUNT_TYPES.FLAT]),
  value: z.number().nonnegative(),
  validFrom: z.date(),
  validTo: z.date(),
  applicableProducts: z.array(z.string()).optional(),
  applicableCategories: z.array(z.string()).optional(),
});

export const CreateDiscountSchema = DiscountSchema.omit({ id: true });
export const UpdateDiscountSchema = DiscountSchema.partial().omit({ id: true });

// New schema for discount query parameters
export const DiscountQuerySchema = z.object({
  availableOnly: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
  populateReferences: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
}).partial(); // Make all query parameters optional

export type Discount = z.infer<typeof DiscountSchema>;
export type CreateDiscountDto = z.infer<typeof CreateDiscountSchema>;
export type UpdateDiscountDto = z.infer<typeof UpdateDiscountSchema>;
export type DiscountQueryDto = z.infer<typeof DiscountQuerySchema>;