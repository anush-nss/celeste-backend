export class CreateOrderDto {
  userId: string;
  items: OrderItem[];
  totalAmount: number;
  discountApplied?: string;
  promotionApplied?: string;
}

export class UpdateOrderDto {
  status?: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
}

export class OrderItem {
  productId: string;
  name: string;
  price: number;
  quantity: number;
}