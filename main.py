from contextlib import asynccontextmanager
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pydantic import BaseModel, Field, ConfigDict, field_validator
import logging
from bson import ObjectId
from dotenv import load_dotenv
import os


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


URL = os.getenv("URL")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.client = AsyncIOMotorClient(URL)
        app.state.db = app.state.client[DB_NAME]
        logger.info("Connected to MongoDB")
        yield
    except Exception as ex:
        logger.exception("MongoDB connection failed: %s", ex)
        raise
    finally:
        app.state.client.close()
        logger.info("MongoDB client disconnected")


app = FastAPI(
    lifespan=lifespan,
    title="Products",
    summary="Control products",
    version="1.0.0",
    openapi_tags=[
        {"name": "products", "description": "Operations with products"}
    ]
)

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


async def get_collection() -> AsyncIOMotorCollection:
    """URL for job in db"""
    logger.info("Getting collection")
    return app.state.db[COLLECTION_NAME]


def validate_object_id(product_id: str) -> ObjectId:
    """Validate ObjectId for document"""
    if not ObjectId.is_valid(product_id):
        logger.warning(f"Invalid ObjectId: {product_id}")
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    logger.debug(f"Valid ObjectId: {product_id}")
    return ObjectId(product_id)


def serialize_doc(doc: dict) -> dict:
    """Serialize document ObjectId for JSON"""
    logger.debug(f"Serializing document: {doc['_id']}")
    doc = doc.copy()
    doc["_id"] = str(doc["_id"])
    return doc


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: Annotated[str | None, Field(alias="_id", default=None)]
    name: str = Field(..., min_length=1, examples=["Milk"], title="Product name", pattern=r"^[a-zA-Z]+$")
    price: float = Field(..., gt=0, examples=[99.99], title="Price for product")



@app.get("/products", response_model=list[Product], response_model_exclude_unset=True, tags=["products"])
async def get_products(
        collection: AsyncIOMotorCollection = Depends(get_collection),
        skip: int = 0,
        limit: int = 10
) -> list[Product]:
    logger.info(f"Fetching products with skip={skip}, limit={limit}")
    products = []

    async for product in collection.find().skip(skip).limit(limit):
        logger.debug(f"Fetched product: {product['_id']}")
        products.append(Product(**serialize_doc(product)))

    logger.info(f"Returning {len(products)} products")
    return products


@app.get("/products/{product_id}", response_model=Product, response_model_exclude_unset=True, tags=["products"])
async def get_product(
        product_id: str,
        collection: AsyncIOMotorCollection = Depends(get_collection)
) -> Product:
    logger.info(f"Fetching product with ID: {product_id}")
    oid = validate_object_id(product_id)
    product = await collection.find_one({"_id": oid})

    if product:
        logger.debug(f"Product found: {oid}")
        return Product(**serialize_doc(product))

    logger.warning(f"Product not found: {product_id}")
    raise HTTPException(status_code=404, detail="Product not found")


@app.post("/products", response_model=Product, response_model_exclude_unset=True, tags=["products"])
async def create_product(
        product: Product,
        collection: AsyncIOMotorCollection = Depends(get_collection)
) -> Product:
    logger.info(f"Creating product: {product.name}")
    product_data = product.model_dump(by_alias=True, exclude={"_id", "id"})

    existing = await collection.find_one({"name": product.name})
    if existing:
        logger.warning(f"Product already exists: {product.name}")
        raise HTTPException(status_code=400, detail="Product already exists")

    result = await collection.insert_one(product_data)
    new_product = await collection.find_one({"_id": result.inserted_id})
    logger.info(f"Product created: {product.name} (ID: {result.inserted_id})")
    return Product(**serialize_doc(new_product))


@app.put("/products/{product_id}", response_model=Product, response_model_exclude_unset=True, tags=["products"])
async def update_product(
        update_model: Product,
        product_id: str,
        collection: AsyncIOMotorCollection = Depends(get_collection)
) -> Product:
    logger.info(f"Updating product with ID: {product_id}")
    product_data = update_model.model_dump(by_alias=True, exclude={"_id", "id"})
    oid = validate_object_id(product_id)

    product = await collection.find_one_and_update(
        {"_id": oid},
        {"$set": product_data},
        return_document=True
    )
    if product:
        logger.info(f"Product updated: {product_id}")
        return Product(**serialize_doc(product))

    logger.warning(f"Product not found for update: {product_id}")
    raise HTTPException(status_code=404, detail="Product not found")


@app.delete("/products/{product_id}", tags=["products"])
async def delete_product(
        product_id: str,
        collection: AsyncIOMotorCollection = Depends(get_collection)
) -> dict:
    logger.info(f"Deleting product with ID: {product_id}")
    oid = validate_object_id(product_id)
    result = await collection.delete_one({"_id": oid})

    if result.deleted_count == 1:
        logger.info(f"Product deleted successfully: {product_id}")
        return {"message": "Product successfully deleted"}

    logger.warning(f"Product not found for deletion: {product_id}")
    raise HTTPException(status_code=404, detail="Product not found")


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)











