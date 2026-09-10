# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Spark 3.3.3 Custom Image with Delta Lake 2.2.0 & AWS S3A SDK
# ==============================================================================

FROM apache/spark:3.3.3

LABEL maintainer="E-Commerce Lakehouse Platform Engineering Team"
LABEL description="Customized Apache Spark 3.3.3 image with Delta Lake 2.2.0, Hadoop AWS, and S3A SDK"

# Switch to root user to install dependencies and JARs
USER root

# Dependency version build arguments
ARG DELTA_VERSION=2.2.0
ARG SCALA_VERSION=2.12
ARG HADOOP_AWS_VERSION=3.3.3
ARG AWS_SDK_VERSION=1.12.367

# Set environment variables
ENV SPARK_HOME=/opt/spark \
    PYTHONUNBUFFERED=1

WORKDIR ${SPARK_HOME}

# Download Delta Lake Core and Storage JARs
RUN curl -fSL "https://repo1.maven.org/maven2/io/delta/delta-core_${SCALA_VERSION}/${DELTA_VERSION}/delta-core_${SCALA_VERSION}-${DELTA_VERSION}.jar" \
        -o "${SPARK_HOME}/jars/delta-core_${SCALA_VERSION}-${DELTA_VERSION}.jar" && \
    curl -fSL "https://repo1.maven.org/maven2/io/delta/delta-storage/${DELTA_VERSION}/delta-storage-${DELTA_VERSION}.jar" \
        -o "${SPARK_HOME}/jars/delta-storage-${DELTA_VERSION}.jar"

# Download Hadoop AWS Connector and AWS Java SDK Bundle for S3A / MinIO access
RUN curl -fSL "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar" \
        -o "${SPARK_HOME}/jars/hadoop-aws-${HADOOP_AWS_VERSION}.jar" && \
    curl -fSL "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar" \
        -o "${SPARK_HOME}/jars/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar"

# Download MySQL Connector/J JDBC Driver for OLTP and Metastore extraction
RUN curl -fSL "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.0.33/mysql-connector-j-8.0.33.jar" \
        -o "${SPARK_HOME}/jars/mysql-connector-j-8.0.33.jar"

# Copy Spark configuration and Hive Metastore client configs
COPY conf/spark-defaults.conf "${SPARK_HOME}/conf/spark-defaults.conf"
COPY conf/hive-site.xml "${SPARK_HOME}/conf/hive-site.xml"

# Set permissions for the default spark user (UID 185)
RUN chown -R 185:185 "${SPARK_HOME}/jars" "${SPARK_HOME}/conf"

# Expose Spark Thrift Server JDBC port (10000) and Web UI port (4040)
EXPOSE 10000 4040

# Switch back to default spark user
USER 185

# Default command launches Spark Thrift Server
CMD ["/opt/spark/sbin/start-thriftserver.sh"]

