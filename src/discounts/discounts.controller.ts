import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';
import { COLLECTION_NAMES } from '../shared/constants';

@ApiTags(COLLECTION_NAMES.DISCOUNTS)
@Controller(COLLECTION_NAMES.DISCOUNTS)
export class DiscountsController {
  // Get all discounts
  @Public()
  @Get()
  findAll(@Query() query: any) {
    // Implementation will be added later
    return [];
  }

  // Get a specific discount by ID
  @Public()
  @Get(':id')
  findOne(@Param('id') id: string) {
    // Implementation will be added later
    return {};
  }
}