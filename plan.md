Tôi muốn refactor hệ thống này thành multiagent system vẫn sử dụng các tech stack hiện tại hãy cung cấp cho tôi một kế hoạch chi tiết để thực hiện điều này.
Chi tiết yêu cầu: 
- Định nghĩa rõ ràng các agent và nhiệm vụ của chúng: 
    + Skill: Agent chịu trách nhiệm về các kỹ năng cụ thể, như xử lý ngôn ngữ tự nhiên, phân tích dữ liệu, hoặc quản lý cơ sở dữ liệu.
    + Task: Agent đảm nhận các nhiệm vụ cụ thể, như thực hiện một tác vụ nhất định hoặc giải quyết một vấn đề cụ thể.
    + Goal: Agent tập trung vào việc đạt được các mục tiêu cụ thể, như hoàn thành một dự án hoặc đạt được một kết quả nhất định.
    + Tool: Agent quản lý các công cụ và tài nguyên cần thiết để thực hiện các nhiệm vụ và đạt được các mục tiêu.
- Thiết kế giao tiếp giữa các agent:
    + Dùng subgraph và message passing để các agent có thể trao đổi thông tin một cách hiệu quả.
- Phân chia nhiệm vụ một cách hợp lý giữa các agent:
    + Mỗi agent sẽ đảm nhận một phần công việc cụ thể dựa trên kỹ năng và nhiệm vụ đã định nghĩa.
- Tối ưu hóa hiệu suất của hệ thống:
    + Sử dụng caching và parallel processing để tăng tốc độ xử lý của các agent.
    + Đảm bảo rằng các agent có thể hoạt động độc lập nhưng vẫn phối hợp hiệu quả với nhau.
- Vấn đề memory management:
    + Vẫn giữ checkpointer như hiện tại
    + Kiểm tra định nghĩa lại các state: sẽ có agent state và global state để quản lý thông tin một cách hiệu quả hơn.
- Thiết kế modular monolithihc architecture:
    + Tạo các module riêng biệt cho từng agent để dễ dàng quản lý và phát triển.
    + Đảm bảo rằng các module có thể tương tác với nhau một cách linh hoạt nhưng vẫn giữ được tính độc lập.
- Kiểm tra và đánh giá hệ thống:
    + Thực hiện các bài kiểm tra đơn vị và tích hợp để đảm bảo rằng các agent hoạt động đúng chức năng và phối hợp hiệu quả với nhau.
- Triển khai và bảo trì hệ thống:
    + Áp dụng langsmith để tracing và giám sát hoạt động của các agent trong hệ thống.
- Tài liệu hóa hệ thống:
    + Cung cấp tài liệu chi tiết về kiến trúc, các agent, và cách thức hoạt động của hệ thống để hỗ trợ việc phát triển và bảo trì trong tương lai.


    