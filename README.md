### Installation

- Initialised docker containers : docker-compose up --build
- Run alembic migrations (mita-server bash) : alembic upgrade head

### Supported Tax services

- EFRIS (Uganda Revenue Authority)
- ZRA (Zambia Revenue Authority)
- Benin (Benin Revenue  Authority)

### Testing

- Run pytest (mita-server bash)  : pytest -v
Do not run in production as tests are using same database as server. will be re-configured :-)

### Deployment

