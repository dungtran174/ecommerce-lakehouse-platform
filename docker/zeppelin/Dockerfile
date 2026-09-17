# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Zeppelin 0.10.1 Notebook Container with PySpark & Delta Lake 2.2.0
# Interactive Exploratory Data Analysis (EDA) & Machine Learning Platform
# ==============================================================================

FROM apache/zeppelin:0.10.1

LABEL maintainer="E-Commerce Lakehouse Platform Engineering Team"
LABEL description="Apache Zeppelin 0.10.1 container with PySpark, Delta Lake 2.2, and MinIO S3A integration"

USER root

# Dependency version build arguments
ARG DELTA_VERSION=2.2.0
ARG SPARK_VERSION=3.3.3

# Set environment variables
ENV ZEPPELIN_HOME=/zeppelin \
    ZEPPELIN_PORT=8080 \
    ZEPPELIN_ADDR=0.0.0.0 \
    SPARK_MASTER="local[*]" \
    PYTHONUNBUFFERED=1

WORKDIR ${ZEPPELIN_HOME}

# Install Python scientific computing and machine learning libraries for PySpark
RUN pip install --no-cache-dir \
        pyspark==${SPARK_VERSION} \
        delta-spark==${DELTA_VERSION} \
        pandas \
        numpy \
        scikit-learn

# Copy customized Zeppelin configuration and pre-configured PySpark interpreter
COPY conf/zeppelin-site.xml ${ZEPPELIN_HOME}/conf/zeppelin-site.xml
COPY conf/interpreter.json ${ZEPPELIN_HOME}/conf/interpreter.json

# Create notebook working directory and configure permissions
RUN mkdir -p ${ZEPPELIN_HOME}/notebook/lakehouse_ml && \
    chown -R 1000:1000 ${ZEPPELIN_HOME}/conf ${ZEPPELIN_HOME}/notebook

# Switch to unprivileged zeppelin user
USER 1000

# Expose Zeppelin web interface port
EXPOSE 8080

# Default entrypoint launches Zeppelin notebook daemon in foreground
CMD ["bin/zeppelin.sh"]
