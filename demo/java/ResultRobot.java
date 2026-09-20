import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

public final class ResultRobot {
    public static void main(String[] args) throws Exception {
        String runId = System.getenv("RCC_RUN_ID");
        Path resultPath = Path.of(System.getenv("RCC_RESULT_PATH"));
        Path temporaryPath = Path.of(resultPath + ".tmp");
        String payload = String.format(
            "{\"version\":1,\"run_id\":\"%s\",\"status\":\"success\"," +
            "\"summary\":\"Processo Java concluido com contrato de resultado\"}",
            runId
        );

        System.out.println("Robo Java executado pelo Zanella Orchestrator");
        Files.writeString(temporaryPath, payload, StandardCharsets.UTF_8);
        Files.move(temporaryPath, resultPath, StandardCopyOption.REPLACE_EXISTING);
    }
}
