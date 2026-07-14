package com.example.demo;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/jarvis") // 定义接口的根路径
public class JarvisController {

    @Autowired
    private JobPublisherService jobPublisherService;

    // 监听 POST 请求
    @PostMapping("/analyze")
    public ResponseEntity<Map<String, String>> triggerAnalysis(@RequestBody Map<String, String> request) {
        // 从请求的 JSON Body 中获取 url 字段
        String targetUrl = String.valueOf(request.get("url"));

        // 基础校验
        if (targetUrl == null || targetUrl.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "URL 不能为空"));
        }

        try {
            // 呼叫 Service 把任务发给 Redis
            jobPublisherService.publishJob(targetUrl);

            // 给调用方返回成功响应
            return ResponseEntity.ok(Map.of(
                    "status", "success",
                    "message", "抓取任务已成功派发给后台 Agent",
                    "target_url", targetUrl
            ));
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }
}
