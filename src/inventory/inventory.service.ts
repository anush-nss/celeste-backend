import { Injectable, NotFoundException } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { Inventory, CreateInventoryDto, UpdateInventoryDto } from './schemas/inventory.schema';

@Injectable()
export class InventoryService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  async findAll(query: any): Promise<Inventory[]> {
    this.logger.log('Finding all inventory items', InventoryService.name);
    const inventory = await this.firestore.getAll(COLLECTION_NAMES.INVENTORY, query);
    return inventory as Inventory[];
  }

  async findOne(id: string): Promise<Inventory> {
    this.logger.log(`Finding inventory item with ID: ${id}`, InventoryService.name);
    const inventoryItem = await this.firestore.getById(COLLECTION_NAMES.INVENTORY, id);
    if (!inventoryItem) {
      throw new NotFoundException(`Inventory item with ID ${id} not found`);
    }
    return inventoryItem as Inventory;
  }

  async create(createInventoryDto: CreateInventoryDto): Promise<Inventory> {
    this.logger.log('Creating new inventory item', InventoryService.name);
    const newInventoryItem = await this.firestore.create(COLLECTION_NAMES.INVENTORY, createInventoryDto);
    return newInventoryItem as Inventory;
  }

  async update(id: string, updateInventoryDto: UpdateInventoryDto): Promise<Inventory> {
    this.logger.log(`Updating inventory item with ID: ${id}`, InventoryService.name);
    const existingInventoryItem = await this.firestore.getById(COLLECTION_NAMES.INVENTORY, id);
    if (!existingInventoryItem) {
      throw new NotFoundException(`Inventory item with ID ${id} not found`);
    }
    const updatedInventoryItem = await this.firestore.update(COLLECTION_NAMES.INVENTORY, id, updateInventoryDto);
    return updatedInventoryItem as Inventory;
  }

  async remove(id: string): Promise<{ id: string }> {
    this.logger.log(`Removing inventory item with ID: ${id}`, InventoryService.name);
    const existingInventoryItem = await this.firestore.getById(COLLECTION_NAMES.INVENTORY, id);
    if (!existingInventoryItem) {
      throw new NotFoundException(`Inventory item with ID ${id} not found`);
    }
    await this.firestore.delete(COLLECTION_NAMES.INVENTORY, id);
    return { id };
  }
}