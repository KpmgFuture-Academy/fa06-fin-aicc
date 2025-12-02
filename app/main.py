import logging
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import chat, handover
from app.core.database import init_db, engine
from app.core.config import settings
from sqlalchemy import text

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bank AICC Dev Server",
    description="AI 상담 챗봇 서버 - LangGraph 기반 워크플로우",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 데이터베이스 초기화 (테이블 생성)
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 DB 테이블 생성 및 연결 확인"""
    try:
        logger.info("데이터베이스 초기화 시작...")
        init_db()
        
        # DB 연결 확인
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        logger.info("데이터베이스 연결 성공")
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}", exc_info=True)
        # DB 연결 실패해도 서버는 시작 (나중에 재시도 가능)
    
    # LLM 설정 확인
    if settings.use_lm_studio:
        logger.info(f"LM Studio 사용 - 모델: {settings.lm_studio_model}, URL: {settings.lm_studio_base_url}")
        logger.info("LM Studio가 실행 중인지 확인하세요: http://localhost:1234")
    else:
        # .env 파일에서만 API 키를 가져옴
        if settings.openai_api_key:
            logger.info(f"✅ OpenAI API 키 로드 완료 (길이: {len(settings.openai_api_key)} 문자)")
            logger.info(f"   API 키 시작: {settings.openai_api_key[:20]}...")
            logger.info(f"   .env 파일에서 로드됨")
        else:
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다!")
            logger.error("   .env 파일에 OPENAI_API_KEY=sk-... 를 추가해주세요.")
            logger.error("   프로젝트 루트 디렉토리에 .env 파일이 있는지 확인하세요.")
            logger.error("   환경 변수는 사용하지 않습니다. 반드시 .env 파일에 설정해야 합니다.")
    
    # 벡터 DB 초기화 확인
    try:
        from ai_engine.vector_store import get_vector_store
        vector_store = get_vector_store()
        logger.info(f"✅ 벡터 DB 초기화 완료 - 경로: {settings.vector_db_path}, 컬렉션: {settings.collection_name}")
    except Exception as e:
        logger.warning(f"⚠️ 벡터 DB 초기화 실패 (RAG 검색은 빈 결과 반환): {str(e)}")
        logger.warning("   벡터 DB는 선택사항입니다. 문서가 없으면 RAG 검색 결과가 비어있을 수 있습니다.")
    
    # Final Classifier 모델 확인 (LoRA 기반 KcELECTRA)
    try:
        from ai_engine.ingestion.bert_financial_intent_classifier.scripts.inference import IntentClassifier
        classifier = IntentClassifier()
        if classifier is not None:
            logger.info("✅ Final Classifier 의도 분류 모델 로드 완료 (38개 카테고리)")
        else:
            logger.warning("⚠️ Final Classifier 모델을 찾을 수 없습니다.")
            logger.warning("   모델 위치: fa06-fin-aicc/models/final_classifier_model/model_final/ 폴더를 확인하세요.")
    except Exception as e:
        logger.warning(f"⚠️ Final Classifier 모델 로드 실패: {str(e)}")
        logger.warning("   모델 위치: fa06-fin-aicc/models/final_classifier_model/model_final/ 폴더를 확인하세요.")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리 작업"""
    logger.info("애플리케이션 종료 중...")


# 라우터 등록 (부품 조립)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(handover.router, prefix="/api/v1/handover", tags=["Handover"])


@app.get("/")
def root():
    """루트 엔드포인트 - 서버 상태 확인"""
    return {
        "status": "Server is running properly!",
        "service": "Bank AICC Dev Server",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트 - 서버 및 DB 상태 확인"""
    try:
        # DB 연결 확인
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "database": "connected",
                "service": "Bank AICC Dev Server"
            }
        )
    except Exception as e:
        logger.error(f"헬스체크 실패: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )