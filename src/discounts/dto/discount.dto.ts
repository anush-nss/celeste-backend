export class CreateDiscountDto {
  name: string;
  type: 'percentage' | 'flat';
  value: number;
  validFrom: Date;
  validTo: Date;
  applicableProducts?: string[];
  applicableCategories?: string[];
}

export class UpdateDiscountDto {
  name?: string;
  type?: 'percentage' | 'flat';
  value?: number;
  validFrom?: Date;
  validTo?: Date;
  applicableProducts?: string[];
  applicableCategories?: string[];
}