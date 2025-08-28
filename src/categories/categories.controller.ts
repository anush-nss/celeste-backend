import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';

@ApiTags('categories')
@Controller('categories')
export class CategoriesController {
  // Get all categories
  @Public()
  @Get()
  findAll(@Query() query: any) {
    // Implementation will be added later
    return [];
  }

  // Get a specific category by ID
  @Public()
  @Get(':id')
  findOne(@Param('id') id: string) {
    // Implementation will be added later
    return {};
  }
}