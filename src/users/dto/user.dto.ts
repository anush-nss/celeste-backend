export class CreateUserDto {
  name: string;
  email: string;
  phone: string;
  address: string;
  role: 'customer' | 'admin';
}

export class UpdateUserDto {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  role?: 'customer' | 'admin';
}

export class AddToWishlistDto {
  productId: string;
}

export class AddToCartDto {
  productId: string;
  quantity: number;
}

export class UpdateCartItemDto {
  quantity: number;
}