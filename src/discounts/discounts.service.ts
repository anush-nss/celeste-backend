import { Injectable, NotFoundException } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { Discount, CreateDiscountDto, UpdateDiscountDto, DiscountQueryDto } from './schemas/discount.schema';
import * as admin from 'firebase-admin';
import { Product } from '../products/schemas/product.schema';
import { Category } from '../categories/schemas/category.schema';

@Injectable()
export class DiscountsService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  async findAll(query: DiscountQueryDto): Promise<Discount[]> {
    this.logger.log('Finding all discounts', DiscountsService.name);
    try {
      const { availableOnly, populateReferences, ...filters } = query;
      let discounts = await this.firestore.getAll(COLLECTION_NAMES.DISCOUNTS, filters) as Discount[];

      if (availableOnly) {
        const now = new Date();
        discounts = discounts.filter(
          (discount) =>
            discount.validFrom <= now && discount.validTo >= now,
        );
      }

      if (populateReferences) {
        const populatedDiscounts = await Promise.all(
          discounts.map(async (discount) => {
            const populatedProducts: Product[] = [];
            const populatedCategories: Category[] = [];

            if (discount.applicableProducts && discount.applicableProducts.length > 0) {
              const productPromises = discount.applicableProducts.map(async (productId) => {
                const product = await this.firestore.getById(COLLECTION_NAMES.PRODUCTS, productId);
                return product as Product;
              });
              populatedProducts.push(...(await Promise.all(productPromises)).filter(Boolean));
            }

            if (discount.applicableCategories && discount.applicableCategories.length > 0) {
              const categoryPromises = discount.applicableCategories.map(async (categoryId) => {
                const category = await this.firestore.getById(COLLECTION_NAMES.CATEGORIES, categoryId);
                return category as Category;
              });
              populatedCategories.push(...(await Promise.all(categoryPromises)).filter(Boolean));
            }

            return {
              ...discount,
              applicableProducts: populatedProducts,
              applicableCategories: populatedCategories,
            } as Discount;
          }),
        );
        return populatedDiscounts;
      }

      return discounts as Discount[];
    } catch (error) {
      this.logger.error(`Failed to fetch discounts: ${error.message}`, error.stack, DiscountsService.name);
      throw error;
    }
  }

  async findOne(id: string): Promise<Discount | null> {
    this.logger.log(`Finding discount with ID: ${id}`, DiscountsService.name);
    try {
      const discount = await this.firestore.getById(COLLECTION_NAMES.DISCOUNTS, id);
      return discount as Discount | null;
    } catch (error) {
      this.logger.error(`Failed to fetch discount ${id}: ${error.message}`, error.stack, DiscountsService.name);
      throw error;
    }
  }

  async create(createDiscountDto: CreateDiscountDto): Promise<Discount> {
    this.logger.log('Creating new discount', DiscountsService.name);
    try {
      const applicableProductsRefs = createDiscountDto.applicableProducts?.map(
        (productId) =>
          this.firestore.getDb().collection(COLLECTION_NAMES.PRODUCTS).doc(productId),
      );
      const applicableCategoriesRefs = createDiscountDto.applicableCategories?.map(
        (categoryId) =>
          this.firestore.getDb().collection(COLLECTION_NAMES.CATEGORIES).doc(categoryId),
      );

      const newDiscount = await this.firestore.create(COLLECTION_NAMES.DISCOUNTS, {
        ...createDiscountDto,
        applicableProducts: applicableProductsRefs || [],
        applicableCategories: applicableCategoriesRefs || [],
      });
      return newDiscount as Discount;
    } catch (error) {
      this.logger.error(`Failed to create discount: ${error.message}`, error.stack, DiscountsService.name);
      throw error;
    }
  }

  async update(id: string, updateDiscountDto: UpdateDiscountDto): Promise<Discount> {
    this.logger.log(`Updating discount with ID: ${id}`, DiscountsService.name);
    try {
      const existingDiscount = await this.firestore.getById(COLLECTION_NAMES.DISCOUNTS, id);
      if (!existingDiscount) {
        throw new NotFoundException(`Discount with ID ${id} not found`);
      }

      let applicableProductsRefs: admin.firestore.DocumentReference[] | undefined;
      if (updateDiscountDto.applicableProducts) {
        applicableProductsRefs = updateDiscountDto.applicableProducts.map(
          (productId) =>
            this.firestore.getDb().collection(COLLECTION_NAMES.PRODUCTS).doc(productId),
        );
      }

      let applicableCategoriesRefs: admin.firestore.DocumentReference[] | undefined;
      if (updateDiscountDto.applicableCategories) {
        applicableCategoriesRefs = updateDiscountDto.applicableCategories.map(
          (categoryId) =>
            this.firestore.getDb().collection(COLLECTION_NAMES.CATEGORIES).doc(categoryId),
        );
      }

      const updatedDiscount = await this.firestore.update(COLLECTION_NAMES.DISCOUNTS, id, {
        ...updateDiscountDto,
        ...(applicableProductsRefs && { applicableProducts: applicableProductsRefs }),
        ...(applicableCategoriesRefs && { applicableCategories: applicableCategoriesRefs }),
      });
      return updatedDiscount as Discount;
    } catch (error) {
      this.logger.error(`Failed to update discount ${id}: ${error.message}`, error.stack, DiscountsService.name);
      throw error;
    }
  }

  async remove(id: string): Promise<{ id: string }> {
    this.logger.log(`Removing discount with ID: ${id}`, DiscountsService.name);
    try {
      const existingDiscount = await this.firestore.getById(COLLECTION_NAMES.DISCOUNTS, id);
      if (!existingDiscount) {
        throw new NotFoundException(`Discount with ID ${id} not found`);
      }
      await this.firestore.delete(COLLECTION_NAMES.DISCOUNTS, id);
      return { id };
    } catch (error) {
      this.logger.error(`Failed to remove discount ${id}: ${error.message}`, error.stack, DiscountsService.name);
      throw error;
    }
  }
}