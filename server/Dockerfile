FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /build

# Cache dependencies layer
COPY server/pom.xml .
COPY server/.mvn .mvn
COPY server/mvnw .
RUN chmod +x mvnw
RUN ./mvnw dependency:go-offline -B

# Build
COPY server/src ./src
RUN ./mvnw package -DskipTests -B

# Runtime
FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=build /build/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT [ "java", "-jar", "app.jar" ]
