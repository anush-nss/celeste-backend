import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';

@ApiTags('promotions')
@Controller('promotions')
export class PromotionsController {
  // Get all promotions
  @Public()
  @Get()
  findAll(@Query() query: any) {
    // Implementation will be added later
    return [];
  }

  // Get a specific promotion by ID
  @Public()
  @Get(':id')
  findOne(@Param('id') id: string) {
    // Implementation will be added later
    return {};
  }
}