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
import { CategoriesService } from './categories.service';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import {
  CreateCategorySchema,
  UpdateCategorySchema,
  type CreateCategoryDto,
  type UpdateCategoryDto,
} from './schemas/category.schema';

@ApiTags(COLLECTION_NAMES.CATEGORIES)
@Controller(COLLECTION_NAMES.CATEGORIES)
export class CategoriesController {
  constructor(private readonly categoriesService: CategoriesService) {}

  // Get all categories
  @Public()
  @Get()
  async findAll(@Query() query: Record<string, any>) {
    const categories = await this.categoriesService.findAll(query);
    return categories;
  }

  // Get a specific category by ID
  @Public()
  @Get(':id')
  async findOne(@Param('id') id: string) {
    const category = await this.categoriesService.findOne(id);
    return category;
  }

  // Create a new category
  @Post()
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(CreateCategorySchema))
  async create(@Body() createCategoryDto: CreateCategoryDto) {
    const category = await this.categoriesService.create(createCategoryDto);
    return category;
  }

  // Update a category
  @Put(':id')
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(UpdateCategorySchema))
  async update(
    @Param('id') id: string,
    @Body() updateCategoryDto: UpdateCategoryDto,
  ) {
    const category = await this.categoriesService.update(id, updateCategoryDto);
    return category;
  }

  // Delete a category
  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    const result = await this.categoriesService.remove(id);
    return result;
  }
}