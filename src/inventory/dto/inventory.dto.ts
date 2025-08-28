export class CreateInventoryDto {
  productId: string;
  stock: number;
}

export class UpdateInventoryDto {
  stock?: number;
}