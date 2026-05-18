package com.yuy.eduflow.ml;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * Manages the Python FastAPI process lifecycle alongside the Spring Boot application.
 * Starts Uvicorn on {@link PostConstruct} and terminates it on {@link PreDestroy}.
 */
@Slf4j
@Component
public class MlApiLifecycleManager {

	private static final int STARTUP_WAIT_SECONDS = 15;
	private static final int HEALTH_CHECK_RETRIES = 10;
	private static final int HEALTH_CHECK_INTERVAL_MS = 2000;

	private final MlApiProperties properties;
	private final MlApiClient mlApiClient;
	private Process pythonProcess;

	public MlApiLifecycleManager(MlApiProperties properties, MlApiClient mlApiClient) {
		this.properties = properties;
		this.mlApiClient = mlApiClient;
	}

	@PostConstruct
	public void start() {
		// If user configured an external URL, skip auto-start
		String configuredUrl = properties.getUrl();
		if (configuredUrl != null && !configuredUrl.contains("127.0.0.1") && !configuredUrl.contains("localhost")) {
			log.info("ML API configured with external URL {}, skipping auto-start", configuredUrl);
			return;
		}
		// If already running, skip
		if (mlApiClient.health()) {
			log.info("ML API already running, skipping auto-start");
			return;
		}

		Path mlDir = resolveMlDir();
		Path venvPython = mlDir.resolve(".venv/bin/python");
		if (!Files.isExecutable(venvPython)) {
			log.warn("ML API venv python not found at {}, skipping auto-start. Start manually: cd server/ml && .venv/bin/python -m uvicorn api.main:app --port 8089", venvPython);
			return;
		}

		List<String> command = new ArrayList<>();
		command.add(venvPython.toString());
		command.add("-m");
		command.add("uvicorn");
		command.add("api.main:app");
		command.add("--host");
		command.add("127.0.0.1");
		command.add("--port");
		command.add(extractPort(configuredUrl, "8089"));
		command.add("--log-level");
		command.add("warning");

		ProcessBuilder builder = new ProcessBuilder(command);
		builder.directory(mlDir.toFile());
		builder.redirectErrorStream(true);

		log.info("Starting ML API server: {}", String.join(" ", command));
		try {
			pythonProcess = builder.start();
			log.info("ML API server process started (PID={})", pythonProcess.pid());
		} catch (IOException e) {
			log.error("Failed to start ML API server: {}", e.getMessage());
			return;
		}

		// Wait for the server to be ready
		for (int i = 0; i < HEALTH_CHECK_RETRIES; i++) {
			try {
				TimeUnit.MILLISECONDS.sleep(HEALTH_CHECK_INTERVAL_MS);
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
				break;
			}
			if (mlApiClient.health()) {
				log.info("ML API server is ready (startup took ~{}s)", (i + 1) * HEALTH_CHECK_INTERVAL_MS / 1000);
				return;
			}
			log.debug("ML API health check attempt {}/{} failed, retrying...", i + 1, HEALTH_CHECK_RETRIES);
		}

		log.warn("ML API server did not become healthy within {}s; check python-ga.log for errors",
			HEALTH_CHECK_RETRIES * HEALTH_CHECK_INTERVAL_MS / 1000);
	}

	@PreDestroy
	public void stop() {
		if (pythonProcess != null && pythonProcess.isAlive()) {
			log.info("Stopping ML API server (PID={})", pythonProcess.pid());
			pythonProcess.destroy();
			try {
				boolean terminated = pythonProcess.waitFor(5, TimeUnit.SECONDS);
				if (!terminated) {
					pythonProcess.destroyForcibly();
				}
			} catch (InterruptedException e) {
				Thread.currentThread().interrupt();
				pythonProcess.destroyForcibly();
			}
			log.info("ML API server stopped");
		}
	}

	private Path resolveMlDir() {
		String configured = properties.getMlDir();
		if (configured != null && !configured.isBlank()) {
			Path path = Path.of(configured);
			if (Files.isDirectory(path.resolve("scripts"))) {
				return path;
			}
		}
		Path cwd = Path.of("").toAbsolutePath();
		Path direct = cwd.resolve("ml");
		if (Files.isDirectory(direct.resolve("scripts"))) {
			return direct;
		}
		Path nested = cwd.resolve("server/ml");
		if (Files.isDirectory(nested.resolve("scripts"))) {
			return nested;
		}
		return direct;
	}

	private String extractPort(String url, String defaultPort) {
		if (url == null || url.isBlank()) return defaultPort;
		int colon = url.lastIndexOf(':');
		if (colon < 0) return defaultPort;
		String portStr = url.substring(colon + 1).replaceAll("[^0-9]", "");
		return portStr.isBlank() ? defaultPort : portStr;
	}
}
