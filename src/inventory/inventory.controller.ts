import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';
import { COLLECTION_NAMES } from '../shared/constants';

@ApiTags(COLLECTION_NAMES.INVENTORY)
@Controller(COLLECTION_NAMES.INVENTORY)
export class InventoryController {
  // Get all inventory items
  @Public()
  @Get()
  findAll(@Query() query: any) {
    // Implementation will be added later
    return [];
  }

  // Get inventory by product ID
  @Public()
  @Get('product/:productId')
  findByProduct(@Param('productId') productId: string) {
    // Implementation will be added later
    return {};
  }

  // Get a specific inventory item by ID
  @Public()
  @Get(':id')
  findOne(@Param('id') id: string) {
    // Implementation will be added later
    return {};
  }
}