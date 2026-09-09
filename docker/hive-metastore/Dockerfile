# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Hive Metastore 3.0.0 Custom Docker Image
# Multi-component metadata service with Hadoop 3.2.0, AWS S3A connectors, and MySQL JDBC
# ==============================================================================

FROM eclipse-temurin:8-jre

LABEL maintainer="E-Commerce Lakehouse Platform Engineering Team"
LABEL description="Apache Hive Standalone Metastore 3.0 with S3A/MinIO and MySQL backend"

# Build arguments for dependency versions
ARG HADOOP_VERSION=3.2.0
ARG HIVE_METASTORE_VERSION=3.0.0
ARG MYSQL_CONNECTOR_VERSION=8.0.33

# Environment variables
ENV HADOOP_VERSION=${HADOOP_VERSION} \
    HIVE_METASTORE_VERSION=${HIVE_METASTORE_VERSION} \
    HADOOP_HOME=/opt/hadoop \
    HIVE_HOME=/opt/hive \
    HADOOP_CLASSPATH=/opt/hadoop/share/hadoop/tools/lib/*:/opt/hive/lib/* \
    PATH=/opt/hive/bin:/opt/hadoop/bin:${PATH}

# Install operating system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        tar \
        bash \
        procps \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt

# Download and install Apache Hadoop (Common and Tools)
RUN curl -fSL "https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz" \
        -o "/tmp/hadoop.tar.gz" && \
    tar -xzf "/tmp/hadoop.tar.gz" -C /opt && \
    mv "/opt/hadoop-${HADOOP_VERSION}" "${HADOOP_HOME}" && \
    rm -f "/tmp/hadoop.tar.gz"

# Download and install Apache Hive Standalone Metastore
RUN curl -fSL "https://archive.apache.org/dist/hive/hive-standalone-metastore-${HIVE_METASTORE_VERSION}/hive-standalone-metastore-${HIVE_METASTORE_VERSION}-bin.tar.gz" \
        -o "/tmp/hive.tar.gz" && \
    tar -xzf "/tmp/hive.tar.gz" -C /opt && \
    mv "/opt/apache-hive-metastore-${HIVE_METASTORE_VERSION}-bin" "${HIVE_HOME}" && \
    rm -f "/tmp/hive.tar.gz"

# Download MySQL Connector/J JDBC Driver into Hive classpath
RUN curl -fSL "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/${MYSQL_CONNECTOR_VERSION}/mysql-connector-j-${MYSQL_CONNECTOR_VERSION}.jar" \
        -o "${HIVE_HOME}/lib/mysql-connector-j-${MYSQL_CONNECTOR_VERSION}.jar"

# Link AWS SDK and Hadoop AWS JARs to Hive Metastore lib for S3A / MinIO access
RUN cp ${HADOOP_HOME}/share/hadoop/tools/lib/hadoop-aws-${HADOOP_VERSION}.jar "${HIVE_HOME}/lib/" && \
    cp ${HADOOP_HOME}/share/hadoop/tools/lib/aws-java-sdk-bundle-*.jar "${HIVE_HOME}/lib/"

# Resolve Guava version conflict (Hive 3.0 uses Guava 19.0 while Hadoop 3.2 uses Guava 27.0)
RUN rm -f "${HIVE_HOME}/lib/guava-19.0.jar" && \
    cp ${HADOOP_HOME}/share/hadoop/common/lib/guava-*.jar "${HIVE_HOME}/lib/"

# Copy default metastore configuration and entrypoint script
COPY conf/metastore-site.xml "${HIVE_HOME}/conf/metastore-site.xml"
COPY entrypoint.sh "${HIVE_HOME}/bin/entrypoint.sh"
RUN chmod +x "${HIVE_HOME}/bin/entrypoint.sh"

# Create dedicated non-root hive user and group for container security
RUN groupadd -r hive --gid=1000 && \
    useradd -r -g hive --uid=1000 -d ${HIVE_HOME} hive && \
    chown -R hive:hive "${HIVE_HOME}" "${HADOOP_HOME}"

# Expose Thrift RPC port
EXPOSE 9083

USER hive
WORKDIR ${HIVE_HOME}

# Container entrypoint initializes DB schema and starts metastore
ENTRYPOINT ["/opt/hive/bin/entrypoint.sh"]

