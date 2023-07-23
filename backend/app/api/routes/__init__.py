from fastapi import APIRouter
from app.api.routes.taxes import router as taxes_router


from app.api.routes.common import router as common_router

router = APIRouter()

router.include_router(taxes_router, prefix="", tags=["Taxmoja"],
                      responses={404: {"description": "oops can't help "
                                                      "you with that!"}})

router.include_router(common_router, prefix="", tags=["Paymoja"],
                      responses={404: {"description": "oops can't help "
                                                      "you with that!"}})

