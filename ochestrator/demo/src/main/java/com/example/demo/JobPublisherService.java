package com.example.demo;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.*;

@Service // 告诉 Spring 这是一个服务组件，由 Spring 自动管理
public class JobPublisherService {
    // 自动注入 Redis 模板，这是我们连接 Docker 中 Redis 的桥梁
    @Autowired
    private StringRedisTemplate redisTemplate;

    // ... 具体的定时方法写在下面 ...
    // @Scheduled 表示这是一个定时任务
    // fixedRate = 30000 意味着每隔 30000 毫秒（30秒），这个方法就会自动执行一次
//    @Scheduled(fixedRate = 30000)
    public void publishJob(String targetUrl) throws Exception {
        try {
            // [阶段 A：构建任务内核]
            // 定义我们要调用 Python 的哪个函数，以及传什么参数
            Map<String, Object> taskCore = new HashMap<>();
            taskCore.put("task", "tasks.scrape_website"); // 对应 Python 代码里的 @app.task(name=...)
            taskCore.put("id", UUID.randomUUID().toString()); // 生成一个唯一的任务追踪 ID
            taskCore.put("args", Collections.singletonList(targetUrl)); // 传给 Python 的网址参数
            taskCore.put("kwargs", new HashMap<>());

            // 将任务内核转换为 JSON，然后进行 Base64 编码
            // 为什么？因为 Celery 默认要求 body 必须是 Base64 编码的格式，防止特殊字符传输丢失
            ObjectMapper mapper = new ObjectMapper();
            String jsonCore = mapper.writeValueAsString(taskCore);
            String base64Body = Base64.getEncoder().encodeToString(jsonCore.getBytes());

            // [阶段 B：封装 Celery 标准信封]
            Map<String, Object> celeryEnvelope = new HashMap<>();
            celeryEnvelope.put("body", base64Body);
            celeryEnvelope.put("content-encoding", "utf-8");
            celeryEnvelope.put("content-type", "application/json");

            // 设置协议属性，告诉 Celery 怎么解码这个信封
            Map<String, Object> properties = new HashMap<>();
            properties.put("body_encoding", "base64");
            properties.put("delivery_info", Map.of("exchange", "", "routing_key", "celery"));
            String uniqueTag = UUID.randomUUID().toString();
            properties.put("delivery_tag", uniqueTag);
            properties.put("correlation_id", uniqueTag);
            celeryEnvelope.put("properties", properties);

            // 将最终的信封转换为 JSON 字符串
            String finalPayload = mapper.writeValueAsString(celeryEnvelope);

            // [阶段 C：投递到 Redis]
            // Celery 默认监听的队列名字就叫 "celery"
            // leftPush 意味着从左边把任务塞进列表，Python Worker 会在右边 (rightPop) 把它取走
            redisTemplate.opsForList().leftPush("celery", finalPayload);

            System.out.println("[中枢] 收到 API 请求，任务已推送至Redis队列 -> 目标: " + targetUrl);

        } catch (Exception e) {
            System.err.println("发布任务时发生错误: " + e.getMessage());
        }
    }

}
