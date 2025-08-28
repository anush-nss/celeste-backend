import { Injectable } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Product } from './schemas/product.schema';
import { FirestoreService } from '../shared/firestore.service';

@Injectable()
export class ProductsService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  // Find all products with optional filtering
  async findAll(query: any): Promise<Product[]> {
    this.logger.log('Finding all products', ProductsService.name);
    try {
      const products = await this.firestore.getAll('products', query);
      return products as Product[];
    } catch (error) {
      this.logger.error(`Failed to fetch products: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }

  // Find a specific product by ID
  async findOne(id: string): Promise<Product | null> {
    this.logger.log(`Finding product with ID: ${id}`, ProductsService.name);
    try {
      const product = await this.firestore.getById('products', id);
      return product as Product | null;
    } catch (error) {
      this.logger.error(`Failed to fetch product ${id}: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }
}