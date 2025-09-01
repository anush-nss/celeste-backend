import { Injectable } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { ProductsService } from './products.service';
import { ProductQueryDto } from './schemas/product.schema';

@Injectable()
export class FeaturedService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly productsService: ProductsService,
  ) {}

  // Find all featured products
  findAll(query: ProductQueryDto) {
    this.logger.log(
      `Finding all featured products with query: ${JSON.stringify(query)}`,
      FeaturedService.name,
    );
    return this.productsService.findAll(query);
  }

  // Find a specific featured product by ID
  findOne(id: string) {
    this.logger.log(`Finding featured product with ID: ${id}`, FeaturedService.name);
    // Implementation will be added later
    return {};
  }
}
