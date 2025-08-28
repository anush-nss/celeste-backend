import { Injectable, NotFoundException } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { Category, CreateCategoryDto, UpdateCategoryDto } from './schemas/category.schema';

@Injectable()
export class CategoriesService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestoreService: FirestoreService,
  ) {}

  async findAll(query: Record<string, any>): Promise<Category[]> {
    this.logger.log('Finding all categories', CategoriesService.name);
    const categories = await this.firestoreService.getAll(COLLECTION_NAMES.CATEGORIES, query);
    return categories as Category[];
  }

  async findOne(id: string): Promise<Category> {
    this.logger.log(`Finding category with ID: ${id}`, CategoriesService.name);
    const category = await this.firestoreService.getById(COLLECTION_NAMES.CATEGORIES, id);
    if (!category) {
      throw new NotFoundException(`Category with ID ${id} not found`);
    }
    return category as Category;
  }

  async create(createCategoryDto: CreateCategoryDto): Promise<Category> {
    this.logger.log('Creating new category', CategoriesService.name);
    const newCategory = await this.firestoreService.create(COLLECTION_NAMES.CATEGORIES, createCategoryDto);
    return newCategory as Category;
  }

  async update(id: string, updateCategoryDto: UpdateCategoryDto): Promise<Category> {
    this.logger.log(`Updating category with ID: ${id}`, CategoriesService.name);
    const existingCategory = await this.firestoreService.getById(COLLECTION_NAMES.CATEGORIES, id);
    if (!existingCategory) {
      throw new NotFoundException(`Category with ID ${id} not found`);
    }
    const updatedCategory = await this.firestoreService.update(COLLECTION_NAMES.CATEGORIES, id, updateCategoryDto);
    return updatedCategory as Category;
  }

  async remove(id: string): Promise<{ id: string }> {
    this.logger.log(`Removing category with ID: ${id}`, CategoriesService.name);
    const existingCategory = await this.firestoreService.getById(COLLECTION_NAMES.CATEGORIES, id);
    if (!existingCategory) {
      throw new NotFoundException(`Category with ID ${id} not found`);
    }
    await this.firestoreService.delete(COLLECTION_NAMES.CATEGORIES, id);
    return { id };
  }
}