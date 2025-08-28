import { z } from 'zod';

export const PromotionSchema = z.object({
  id: z.string().optional(),
  title: z.string().min(1),
  description: z.string().optional(),
  bannerUrl: z.string().optional(),
  validFrom: z.date(),
  validTo: z.date(),
  promotionType: z.enum(['BOGO', 'FlashSale', 'Seasonal']),
  applicableProducts: z.array(z.string()).optional(),
  applicableCategories: z.array(z.string()).optional(),
});

export const CreatePromotionSchema = PromotionSchema.omit({ id: true });
export const UpdatePromotionSchema = PromotionSchema.partial().omit({ id: true });

export type Promotion = z.infer<typeof PromotionSchema>;
export type CreatePromotionDto = z.infer<typeof CreatePromotionSchema>;
export type UpdatePromotionDto = z.infer<typeof UpdatePromotionSchema>;