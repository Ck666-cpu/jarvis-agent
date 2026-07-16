# 第一阶段：使用 Maven 镜像进行编译打包
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /app

# 复制 pom.xml 和源码
COPY demo/pom.xml .
COPY demo/src ./src

# 打包并跳过测试以加快构建速度
RUN mvn clean package -DskipTests

# 第二阶段：运行阶段，使用纯净的 JRE 环境（让镜像体积更小）
FROM eclipse-temurin:17-jre
WORKDIR /app

# 把第一阶段打包好的 jar 文件复制过来
COPY --from=builder /app/target/*.jar app.jar

# 暴露 Spring Boot 默认端口
EXPOSE 8080

# 启动命令
ENTRYPOINT ["java", "-jar", "app.jar"]