# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Ranger 2.4.0 Admin Service Custom Docker Image
# Centralized RBAC authorization, dynamic column masking & audit logging
# ==============================================================================

FROM eclipse-temurin:8-jre

LABEL maintainer="E-Commerce Lakehouse Platform Engineering Team"
LABEL description="Apache Ranger 2.4.0 Admin Security Management Server with PostgreSQL backend"

# Build arguments for dependency versions
ARG RANGER_VERSION=2.4.0
ARG POSTGRES_CONNECTOR_VERSION=42.6.0

# Environment variables
ENV RANGER_VERSION=${RANGER_VERSION} \
    RANGER_HOME=/opt/ranger-admin \
    JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/ranger-admin:${PATH} \
    PYTHONUNBUFFERED=1

# Install operating system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        tar \
        bash \
        procps \
        netcat-openbsd \
        postgresql-client \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for lightweight DB connectivity
RUN pip3 install --no-cache-dir psycopg2-binary==2.9.9

WORKDIR /opt

# Create Ranger directory structure
RUN mkdir -p ${RANGER_HOME}/ews/webapp/WEB-INF/lib \
             ${RANGER_HOME}/conf \
             ${RANGER_HOME}/logs \
             ${RANGER_HOME}/scripts

# Download PostgreSQL JDBC Driver into Ranger classpath
RUN curl -fSL "https://repo1.maven.org/maven2/org/postgresql/postgresql/${POSTGRES_CONNECTOR_VERSION}/postgresql-${POSTGRES_CONNECTOR_VERSION}.jar" \
        -o "${RANGER_HOME}/ews/webapp/WEB-INF/lib/postgresql-${POSTGRES_CONNECTOR_VERSION}.jar"

# Copy Ranger installation properties, server implementation, and entrypoint
COPY conf/install.properties "${RANGER_HOME}/conf/install.properties"
COPY scripts/ranger_admin_server.py "${RANGER_HOME}/scripts/ranger_admin_server.py"
COPY entrypoint.sh "${RANGER_HOME}/entrypoint.sh"
RUN chmod +x "${RANGER_HOME}/entrypoint.sh"

# Create dedicated non-root ranger user and group for container security
RUN groupadd -r ranger --gid=1000 && \
    useradd -r -g ranger --uid=1000 -d ${RANGER_HOME} -s /bin/bash ranger && \
    chown -R ranger:ranger ${RANGER_HOME}

# Expose Ranger Web UI and REST API port
EXPOSE 6080

# Switch to non-root user
USER ranger
WORKDIR ${RANGER_HOME}

ENTRYPOINT ["/opt/ranger-admin/entrypoint.sh"]
CMD ["ranger-admin"]
