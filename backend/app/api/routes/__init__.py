from fastapi import APIRouter
from app.api.routes.taxes import router as taxes_router
from app.api.routes.bitrix import router as bitrix_router
from app.api.routes.dear import router as dear_router
from app.api.routes.xero import router as xero_router
from app.api.routes.common import router as common_router

router = APIRouter()

router.include_router(taxes_router, prefix="/taxmoja", tags=["Taxmoja"],
                      responses={404: {"description": "oops can't help "
                                                      "you with that!"}})

router.include_router(bitrix_router, prefix='/bitrix24',
                      tags=['Bitrix24'],
                      responses={404: {"description": "oops can't help you with that!"}}, )

router.include_router(xero_router, prefix='/xero',
                      tags=['Xero'],
                      responses={404: {"description": "oops can't help you with that!"}}, )


router.include_router(dear_router, prefix='/dear',
                      tags=['Dear'],
                      responses={404: {"description": "oops can't help you with that!"}}, )

router.include_router(common_router, prefix="", tags=["Paymoja"],
                      responses={404: {"description": "oops can't help "
                                                      "you with that!"}})

