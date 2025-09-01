import {
  Controller,
  Get,
  Param,
  Query,
  Post,
  Put,
  Delete,
  Body,
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';
import { Roles } from '../auth/roles.decorator';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';
import { InventoryService } from './inventory.service';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import * as inventorySchema from './schemas/inventory.schema';

@ApiTags(COLLECTION_NAMES.INVENTORY)
@Controller(COLLECTION_NAMES.INVENTORY)
export class InventoryController {
  constructor(private readonly inventoryService: InventoryService) {}

  @Get()
  @Roles(USER_ROLES.CUSTOMER, USER_ROLES.ADMIN)
  async findAll(@Query() query: any) {
    const inventory = await this.inventoryService.findAll(query);
    return inventory;
  }

  @Get(':id')
  @Roles(USER_ROLES.CUSTOMER, USER_ROLES.ADMIN)
  async findOne(@Param('id') id: string) {
    const inventoryItem = await this.inventoryService.findOne(id);
    return inventoryItem;
  }

  @Post()
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(inventorySchema.CreateInventorySchema))
  async create(@Body() createInventoryDto: inventorySchema.CreateInventoryDto) {
    const newInventoryItem =
      await this.inventoryService.create(createInventoryDto);
    return newInventoryItem;
  }

  @Put(':id')
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(inventorySchema.UpdateInventorySchema))
  async update(
    @Param('id') id: string,
    @Body() updateInventoryDto: inventorySchema.UpdateInventoryDto,
  ) {
    const updatedInventoryItem = await this.inventoryService.update(
      id,
      updateInventoryDto,
    );
    return updatedInventoryItem;
  }

  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    const result = await this.inventoryService.remove(id);
    return result;
  }
}
