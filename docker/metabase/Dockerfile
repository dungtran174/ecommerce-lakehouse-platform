# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Metabase Business Intelligence & Analytics Dashboard Container
# Pre-configured with Trino JDBC Driver for Lakehouse MPP Query Serving
# ==============================================================================

FROM metabase/metabase:v0.48.4

LABEL maintainer="E-Commerce Lakehouse Platform Engineering Team"
LABEL description="Metabase v0.48.4 container with Trino JDBC 435 driver pre-installed"

USER root

# Dependency version build arguments
ARG TRINO_JDBC_VERSION=435

# Set environment variables
ENV MB_PLUGINS_DIR=/plugins \
    JAVA_OPTS="-XX:+IgnoreUnrecognizedVMOptions -Dfile.encoding=UTF-8"

# Create plugins directory and install Trino JDBC driver
RUN mkdir -p ${MB_PLUGINS_DIR} && \
    curl -fSL "https://repo1.maven.org/maven2/io/trino/trino-jdbc/${TRINO_JDBC_VERSION}/trino-jdbc-${TRINO_JDBC_VERSION}.jar" \
        -o "${MB_PLUGINS_DIR}/trino-jdbc-${TRINO_JDBC_VERSION}.jar" && \
    chmod 644 "${MB_PLUGINS_DIR}/trino-jdbc-${TRINO_JDBC_VERSION}.jar" && \
    chown -R 2000:2000 ${MB_PLUGINS_DIR}

# Switch back to default unprivileged metabase user (UID 2000)
USER 2000

# Expose default Metabase HTTP web interface port
EXPOSE 3000
