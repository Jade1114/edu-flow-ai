package com.yuy.eduflow.ml;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "app.ml.api")
public class MlApiProperties {
	/** FastAPI server URL, e.g. http://127.0.0.1:8000 */
	private String url = "http://127.0.0.1:8000";
	/** Path to the ml/ directory (auto-resolved if empty) */
	private String mlDir = "";
}
