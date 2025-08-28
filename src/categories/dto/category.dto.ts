export class CreateCategoryDto {
  name: string;
  description: string;
  imageUrl: string;
  parentCategoryId: string | null;
}

export class UpdateCategoryDto {
  name?: string;
  description?: string;
  imageUrl?: string;
  parentCategoryId?: string | null;
}