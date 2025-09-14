"""
Generic SQLAlchemy utilities for safe model conversion
"""

from typing import Any, Dict, List, Optional, Set, Type, Union, Sequence
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from src.shared.utils import get_logger

logger = get_logger(__name__)


def sqlalchemy_to_dict(
    obj: DeclarativeBase,
    include_relationships: Optional[Set[str]] = None,
    exclude_relationships: Optional[Set[str]] = None,
    max_depth: int = 2
) -> Dict[str, Any]:
    """
    Convert SQLAlchemy model instance to dictionary safely, avoiding MissingGreenlet errors.
    
    Args:
        obj: SQLAlchemy model instance
        include_relationships: Set of relationship names to include (None = include all loaded)
        exclude_relationships: Set of relationship names to exclude
        max_depth: Maximum depth for nested relationships (prevents infinite recursion)
        
    Returns:
        Dictionary representation of the model
    """
    if max_depth <= 0:
        return {}
        
    if obj is None:
        return {}
    
    # Get the model's mapper
    mapper = inspect(obj.__class__)
    result = {}
    
    # Handle regular columns
    for column in mapper.columns:
        column_name = column.name
        try:
            value = getattr(obj, column_name)
            result[column_name] = value
        except Exception as e:
            logger.warning(f"Error accessing column {column_name}: {e}")
            result[column_name] = None
    
    # Handle relationships
    include_relationships = include_relationships or set()
    exclude_relationships = exclude_relationships or set()
    
    for relationship in mapper.relationships:
        rel_name = relationship.key
        
        # Skip if explicitly excluded
        if exclude_relationships and rel_name in exclude_relationships:
            result[rel_name] = None
            continue
            
        # Only include if specifically requested or if it's already loaded
        should_include = (
            rel_name in include_relationships or
            (not include_relationships and _is_relationship_loaded(obj, rel_name))
        )
        
        if should_include:
            try:
                rel_value = getattr(obj, rel_name)
                
                if rel_value is None:
                    result[rel_name] = None
                elif hasattr(rel_value, '__iter__') and not isinstance(rel_value, (str, bytes)):
                    # Handle one-to-many or many-to-many relationships
                    result[rel_name] = [
                        sqlalchemy_to_dict(
                            item, 
                            include_relationships=include_relationships,
                            exclude_relationships=exclude_relationships,
                            max_depth=max_depth - 1
                        )
                        for item in rel_value
                    ]
                else:
                    # Handle one-to-one or many-to-one relationships
                    if isinstance(rel_value, DeclarativeBase):
                        result[rel_name] = sqlalchemy_to_dict(
                            rel_value,
                            include_relationships=include_relationships,
                            exclude_relationships=exclude_relationships,
                            max_depth=max_depth - 1
                        )
            except Exception as e:
                logger.warning(f"Error accessing relationship {rel_name}: {e}")
                result[rel_name] = None
        else:
            result[rel_name] = None
    
    return result


def _is_relationship_loaded(obj: DeclarativeBase, relationship_name: str) -> bool:
    """
    Check if a relationship is already loaded without triggering lazy loading.
    """
    try:
        # Check if the relationship attribute is in the object's __dict__
        # This means it's been loaded and won't trigger a database query
        return relationship_name in obj.__dict__
    except Exception:
        return False


def safe_model_validate(pydantic_class: Type, sqlalchemy_obj: DeclarativeBase, **kwargs) -> Any:
    """
    Safely convert SQLAlchemy model to Pydantic model using the generic converter.
    
    Args:
        pydantic_class: The Pydantic model class
        sqlalchemy_obj: The SQLAlchemy model instance
        **kwargs: Additional arguments for sqlalchemy_to_dict
        
    Returns:
        Pydantic model instance
    """
    if sqlalchemy_obj is None:
        return None
        
    obj_dict = sqlalchemy_to_dict(sqlalchemy_obj, **kwargs)
    return pydantic_class.model_validate(obj_dict)


def safe_model_validate_list(
    pydantic_class: Type, 
    sqlalchemy_objs: Sequence[DeclarativeBase], 
    **kwargs
) -> List[Any]:
    """
    Safely convert list of SQLAlchemy models to list of Pydantic models.
    
    Args:
        pydantic_class: The Pydantic model class
        sqlalchemy_objs: List of SQLAlchemy model instances
        **kwargs: Additional arguments for sqlalchemy_to_dict
        
    Returns:
        List of Pydantic model instances
    """
    if not sqlalchemy_objs:
        return []
        
    return [
        safe_model_validate(pydantic_class, obj, **kwargs)
        for obj in sqlalchemy_objs
    ]