export class CreateProductDto {
  name: string;
  description: string;
  price: number;
  stock: number;
  unit: string;
  categoryId: string;
  imageUrl: string;
}

export class UpdateProductDto {
  name?: string;
  description?: string;
  price?: number;
  stock?: number;
  unit?: string;
  categoryId?: string;
  imageUrl?: string;
}