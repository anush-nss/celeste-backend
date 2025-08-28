import { Injectable, NotFoundException } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { Product, CreateProductDto, UpdateProductDto, ProductQueryDto } from './schemas/product.schema';
import { Discount } from '../discounts/schemas/discount.schema';
import * as admin from 'firebase-admin';

@Injectable()
export class ProductsService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  async findAll(query: ProductQueryDto): Promise<Product[]> {
    this.logger.log('Finding all products', ProductsService.name);
    try {
      const { limit, offset, includeDiscounts, ...filters } = query;
      const products = await this.firestore.getAll(COLLECTION_NAMES.PRODUCTS, {
        limit,
        offset,
        ...filters,
      }) as Product[];

      if (includeDiscounts) {
        const productIds = products.map((p) => p.id);
        const discounts = await this.firestore.getAll(COLLECTION_NAMES.DISCOUNTS, {
          applicableProducts: productIds,
        }) as Discount[];

        return products.map((product) => {
          const applicableDiscounts = discounts.filter((discount) =>
            discount.applicableProducts?.includes(product.id),
          );
          return { ...product, discounts: applicableDiscounts } as Product;
        });
      }

      return products as Product[];
    } catch (error) {
      this.logger.error(`Failed to fetch products: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }

  async findOne(id: string): Promise<Product | null> {
    this.logger.log(`Finding product with ID: ${id}`, ProductsService.name);
    try {
      const product = await this.firestore.getById(COLLECTION_NAMES.PRODUCTS, id);
      return product as Product | null;
    } catch (error) {
      this.logger.error(`Failed to fetch product ${id}: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }

  async create(createProductDto: CreateProductDto): Promise<Product> {
    this.logger.log('Creating new product', ProductsService.name);
    try {
      const categoryRef = this.firestore.getDb().collection(COLLECTION_NAMES.CATEGORIES).doc(createProductDto.categoryId);
      const newProduct = await this.firestore.create(COLLECTION_NAMES.PRODUCTS, {
        ...createProductDto,
        categoryId: categoryRef,
      });
      return newProduct as Product;
    } catch (error) {
      this.logger.error(`Failed to create product: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }

  async update(id: string, updateProductDto: UpdateProductDto): Promise<Product> {
    this.logger.log(`Updating product with ID: ${id}`, ProductsService.name);
    try {
      const existingProduct = await this.firestore.getById(COLLECTION_NAMES.PRODUCTS, id);
      if (!existingProduct) {
        throw new NotFoundException(`Product with ID ${id} not found`);
      }

      let categoryRef: admin.firestore.DocumentReference | undefined;
      if (updateProductDto.categoryId) {
        categoryRef = this.firestore.getDb().collection(COLLECTION_NAMES.CATEGORIES).doc(updateProductDto.categoryId);
      }

      const updatedProduct = await this.firestore.update(COLLECTION_NAMES.PRODUCTS, id, {
        ...updateProductDto,
        ...(categoryRef && { categoryId: categoryRef }),
      });
      return updatedProduct as Product;
    } catch (error) {
      this.logger.error(`Failed to update product ${id}: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }

  async remove(id: string): Promise<{ id: string }> {
    this.logger.log(`Removing product with ID: ${id}`, ProductsService.name);
    try {
      const existingProduct = await this.firestore.getById(COLLECTION_NAMES.PRODUCTS, id);
      if (!existingProduct) {
        throw new NotFoundException(`Product with ID ${id} not found`);
      }
      await this.firestore.delete(COLLECTION_NAMES.PRODUCTS, id);
      return { id };
    } catch (error) {
      this.logger.error(`Failed to remove product ${id}: ${error.message}`, error.stack, ProductsService.name);
      throw error;
    }
  }
}