export class CreatePromotionDto {
  title: string;
  description: string;
  bannerUrl: string;
  validFrom: Date;
  validTo: Date;
  promotionType: 'BOGO' | 'FlashSale' | 'Seasonal';
  applicableProducts?: string[];
  applicableCategories?: string[];
}

export class UpdatePromotionDto {
  title?: string;
  description?: string;
  bannerUrl?: string;
  validFrom?: Date;
  validTo?: Date;
  promotionType?: 'BOGO' | 'FlashSale' | 'Seasonal';
  applicableProducts?: string[];
  applicableCategories?: string[];
}