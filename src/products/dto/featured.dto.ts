export class CreateFeaturedDto {
  productId: string;
  featuredFrom: Date;
  featuredTo: Date;
}

export class UpdateFeaturedDto {
  productId?: string;
  featuredFrom?: Date;
  featuredTo?: Date;
}