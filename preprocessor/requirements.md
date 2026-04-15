# Requirements Document

## Introduction

RAG(Retrieval-Augmented Generation)를 위한 문서 전처리 웹 툴이다. 문서(PDF, Word, Web Page)를 파싱하여 text, image, table 등의 객체로 구분하고, 사용자의 의도를 반영하여 노이즈 제거, 소제목 요약문 생성, 테이블/이미지 후처리를 수행한 뒤 최종 JSON 파일로 출력한다. 청킹과 임베딩은 이후 RAG 시스템에서 처리하므로 본 툴의 범위에 포함하지 않는다. Python(uv) 환경에서 동작하며, 프론트엔드 CSS는 Ant Design(antd)을 사용한다.

## Glossary

- **Preprocessing_Tool**: 문서 전처리 웹 애플리케이션 전체 시스템
- **Parser**: 문서(PDF, Word, Web Page)를 text, image, table 객체로 분류하는 1차 파싱 모듈
- **Viewer**: 좌측 원본 문서와 우측 처리 결과를 나란히 보여주는 웹 화면 컴포넌트
- **Noise_Remover**: 헤더, 푸터, 페이지 번호 등 불필요한 요소를 제거하는 모듈
- **Summary_Generator**: 소제목 하위에 LLM을 통해 요약 문장을 생성하는 모듈
- **Table_Processor**: 테이블 객체를 pandas 변환 또는 LLM text flattening으로 후처리하는 모듈
- **Image_Processor**: 이미지 객체를 텍스트 링크 연결 또는 VLM 해석으로 후처리하는 모듈
- **MD_Exporter**: 전처리 완료된 결과를 Markdown 파일로 출력하는 모듈
- **API_Key_Manager**: 외부 LLM/VLM API 키를 저장하고 불러오는 관리 모듈
- **Object_Box**: 파싱된 image 또는 table 객체를 시각적으로 구분하는 박스 UI 요소
- **Confirmed_Status**: 사용자가 후처리 결과를 확인(Confirm)한 상태 표시

## Requirements

### Requirement 1: 문서 업로드 및 파싱

**User Story:** As a 사용자, I want 다양한 형식의 문서를 업로드하여 text, image, table 객체로 자동 분류되길, so that 문서 내 각 요소를 개별적으로 전처리할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 PDF 파일을 업로드하면, THE Parser SHALL 문서 내용을 text, image, table 객체로 분류하여 반환한다.
2. WHEN 사용자가 Word 파일을 업로드하면, THE Parser SHALL 문서 내용을 text, image, table 객체로 분류하여 반환한다.
3. WHEN 사용자가 Web Page URL을 입력하면, THE Parser SHALL 해당 페이지 내용을 text, image, table 객체로 분류하여 반환한다.
4. THE Viewer SHALL image 객체와 table 객체를 Object_Box로 감싸서 text 객체와 시각적으로 구분하여 표시한다.
5. IF 지원하지 않는 파일 형식이 업로드되면, THEN THE Preprocessing_Tool SHALL "지원하지 않는 파일 형식입니다"라는 오류 메시지를 표시한다.
6. IF 파싱 중 오류가 발생하면, THEN THE Parser SHALL 오류 내용을 사용자에게 표시하고 이전 상태를 유지한다.

### Requirement 2: 원본-결과 분할 화면

**User Story:** As a 사용자, I want 원본 문서와 전처리 결과를 나란히 비교하며 볼 수 있길, so that 전처리 결과를 원본과 대조하여 검증할 수 있다.

#### Acceptance Criteria

1. THE Viewer SHALL 화면 좌측에 원본 문서를, 우측에 전처리 결과를 나란히 표시한다.
2. WHEN 전처리 작업(노이즈 제거, 요약 생성 등)이 수행되면, THE Viewer SHALL 우측 결과 화면을 즉시 갱신한다.
3. THE Viewer SHALL Ant Design(antd) 컴포넌트를 사용하여 UI를 렌더링한다.

### Requirement 3: 노이즈 제거

**User Story:** As a 사용자, I want 헤더, 푸터, 페이지 번호 등 불필요한 요소를 제거할 수 있길, so that 핵심 내용만 남은 깨끗한 문서를 얻을 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 노이즈 제거 버튼을 클릭하면, THE Noise_Remover SHALL 헤더, 푸터, 페이지 번호를 문서에서 제거한다.
2. WHEN 노이즈 제거가 완료되면, THE Viewer SHALL 우측 결과 화면에 노이즈가 제거된 문서를 표시한다.
3. THE Noise_Remover SHALL 커스텀 노이즈 정의를 위한 입력창을 제공한다.
4. WHEN 사용자가 커스텀 입력창에 헤더 패턴을 정의하면, THE Noise_Remover SHALL 해당 패턴과 일치하는 텍스트를 헤더로 인식하여 제거한다.
5. WHEN 사용자가 커스텀 입력창에 푸터 패턴을 정의하면, THE Noise_Remover SHALL 해당 패턴과 일치하는 텍스트를 푸터로 인식하여 제거한다.
6. WHEN 사용자가 커스텀 입력창에 페이지 번호 패턴을 정의하면, THE Noise_Remover SHALL 해당 패턴과 일치하는 텍스트를 페이지 번호로 인식하여 제거한다.

### Requirement 4: 소제목 요약문 생성

**User Story:** As a 사용자, I want 소제목 아래에 LLM이 생성한 요약 문장을 삽입할 수 있길, so that 문서의 각 섹션 내용을 빠르게 파악할 수 있다.

#### Acceptance Criteria

1. WHEN 문서가 파싱되면, THE Parser SHALL 문서 내 소제목을 자동으로 식별한다.
2. WHEN 사용자가 소제목 요약 생성을 요청하면, THE Summary_Generator SHALL LLM을 통해 각 소제목 하위 내용의 요약 문장을 생성하여 소제목 아래에 삽입한다.
3. WHEN 사용자가 소제목으로 지정되지 않은 텍스트를 선택하여 소제목으로 지정하면, THE Summary_Generator SHALL 해당 텍스트를 소제목으로 등록하고 요약 문장을 생성한다.
4. WHEN 사용자가 임의의 텍스트를 선택하여 요약문 생성을 요청하면, THE Summary_Generator SHALL 해당 텍스트 하위 내용에 대한 요약 문장을 LLM을 통해 생성한다.
5. IF API_Key_Manager에 유효한 LLM API 키가 등록되어 있지 않으면, THEN THE Summary_Generator SHALL "LLM API 키를 먼저 등록해주세요"라는 안내 메시지를 표시한다.

### Requirement 5: 수동 객체 지정

**User Story:** As a 사용자, I want Parser가 인식하지 못한 table이나 image 영역을 수동으로 지정할 수 있길, so that 파싱 누락 없이 모든 객체를 처리할 수 있다.

#### Acceptance Criteria

1. THE Viewer SHALL 수동 테이블 지정 버튼과 수동 이미지 지정 버튼을 제공한다.
2. WHEN 사용자가 수동 테이블 지정 버튼을 클릭한 후 문서 영역을 선택하면, THE Preprocessing_Tool SHALL 해당 영역을 table 객체로 등록하고 Object_Box로 표시한다.
3. WHEN 사용자가 수동 이미지 지정 버튼을 클릭한 후 문서 영역을 선택하면, THE Preprocessing_Tool SHALL 해당 영역을 image 객체로 등록하고 Object_Box로 표시한다.

### Requirement 6: 테이블 후처리

**User Story:** As a 사용자, I want 테이블 객체를 클릭하여 구조화된 데이터로 변환하고 필요시 LLM으로 보정할 수 있길, so that 정확한 테이블 데이터를 JSON에 포함시킬 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 table Object_Box를 클릭하면, THE Table_Processor SHALL pandas를 통해 변환된 테이블 결과값을 표시한다.
2. WHEN 사용자가 "LLM을 통해 text flattening 하기" 버튼을 클릭하면, THE Table_Processor SHALL LLM을 통해 테이블을 텍스트로 변환한 결과값을 표시한다.
3. THE Table_Processor SHALL 변환 결과값을 사용자가 직접 편집할 수 있는 텍스트 편집 영역을 제공한다.
4. THE Table_Processor SHALL 수정 요청사항을 입력할 수 있는 채팅 입력창을 제공한다.
5. WHEN 사용자가 채팅 입력창에 수정 요청을 입력하면, THE Table_Processor SHALL LLM을 통해 수정된 결과값을 표시한다.
6. WHEN 사용자가 Confirm 버튼을 클릭하면, THE Table_Processor SHALL 현재 결과값을 확정하고 해당 table Object_Box에 Confirmed_Status를 표시한다.
7. IF API_Key_Manager에 유효한 LLM API 키가 등록되어 있지 않은 상태에서 LLM 기능을 요청하면, THEN THE Table_Processor SHALL "LLM API 키를 먼저 등록해주세요"라는 안내 메시지를 표시한다.

### Requirement 7: 이미지 후처리

**User Story:** As a 사용자, I want 이미지 객체를 클릭하여 텍스트 링크 연결 또는 VLM 해석 중 처리 방식을 선택할 수 있길, so that 이미지 정보를 RAG에 적합한 형태로 변환할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 image Object_Box를 클릭하면, THE Image_Processor SHALL "지정 텍스트에 링크로 연결" 옵션과 "VLM으로 이미지 해석" 옵션을 표시한다.
2. WHEN 사용자가 "지정 텍스트에 링크로 연결"을 선택하면, THE Image_Processor SHALL 해당 이미지를 별도 폴더에 저장하고, 사용자가 지정한 텍스트에 이미지 경로를 `<경로>` 형식으로 삽입한다.
3. WHEN 사용자가 "VLM으로 이미지 해석"을 선택하면, THE Image_Processor SHALL VLM을 통해 이미지를 텍스트로 해석한 결과값을 표시한다.
4. THE Image_Processor SHALL VLM 해석 결과값을 사용자가 직접 편집할 수 있는 텍스트 편집 영역을 제공한다.
5. THE Image_Processor SHALL 수정 요청사항을 입력할 수 있는 채팅 입력창을 제공한다.
6. WHEN 사용자가 채팅 입력창에 수정 요청을 입력하면, THE Image_Processor SHALL VLM/LLM을 통해 수정된 결과값을 표시한다.
7. WHEN 사용자가 Confirm 버튼을 클릭하면, THE Image_Processor SHALL 현재 결과값을 확정하고 해당 image Object_Box에 Confirmed_Status를 표시한다.
8. IF API_Key_Manager에 유효한 VLM/LLM API 키가 등록되어 있지 않은 상태에서 VLM 기능을 요청하면, THEN THE Image_Processor SHALL "VLM API 키를 먼저 등록해주세요"라는 안내 메시지를 표시한다.

### Requirement 8: API 키 관리

**User Story:** As a 사용자, I want LLM/VLM API 키를 저장하고 불러올 수 있길, so that 외부 AI 서비스를 활용한 전처리 기능을 사용할 수 있다.

#### Acceptance Criteria

1. THE API_Key_Manager SHALL API 키를 입력하고 저장할 수 있는 설정 화면을 제공한다.
2. WHEN 사용자가 API 키를 입력하고 저장 버튼을 클릭하면, THE API_Key_Manager SHALL 해당 키를 로컬에 안전하게 저장한다.
3. WHEN LLM 또는 VLM 기능이 호출되면, THE API_Key_Manager SHALL 저장된 API 키를 불러와 해당 서비스에 전달한다.
4. IF 저장된 API 키가 유효하지 않으면, THEN THE API_Key_Manager SHALL "API 키가 유효하지 않습니다. 설정에서 확인해주세요"라는 오류 메시지를 표시한다.

### Requirement 9: Markdown 파일 출력

**User Story:** As a 사용자, I want 전처리가 완료된 문서를 Markdown 파일로 내보낼 수 있길, so that 이후 RAG 시스템에서 청킹 및 임베딩 처리를 수행할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 MD 내보내기 버튼을 클릭하면, THE MD_Exporter SHALL 전처리된 모든 객체(text, table, image)를 포함한 Markdown 파일을 생성한다.
2. THE MD_Exporter SHALL 각 객체의 유형(text, table, image), 내용, 순서 정보를 Markdown 구조에 포함한다.
3. THE MD_Exporter SHALL 이미지 링크 경로 정보를 Markdown 이미지 문법(`![alt](경로)`)으로 포함한다.
4. THE MD_Exporter SHALL 소제목 요약문 정보를 Markdown 헤딩(`##`, `###`) 형식으로 포함한다.
5. IF 미확인(Confirm되지 않은) table 또는 image 객체가 존재하면, THEN THE MD_Exporter SHALL "확인되지 않은 객체가 있습니다. 모든 객체를 확인한 후 내보내기를 진행해주세요"라는 경고 메시지를 표시한다.

### Requirement 10: Markdown 라운드트립 검증

**User Story:** As a 사용자, I want 생성된 Markdown을 다시 로드하여 이전 전처리 상태를 복원할 수 있길, so that 전처리 작업을 이어서 수행하거나 결과를 검증할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 기존 Markdown 파일을 로드하면, THE Preprocessing_Tool SHALL Markdown 내 모든 객체를 파싱하여 전처리 결과 화면에 복원한다.
2. FOR ALL 유효한 전처리 결과 객체에 대해, Markdown 내보내기 후 다시 로드하면 THE Preprocessing_Tool SHALL 동일한 객체 구조와 내용을 복원한다 (라운드트립 속성).
3. IF Markdown 파일 형식이 올바르지 않으면, THEN THE Preprocessing_Tool SHALL "올바르지 않은 Markdown 형식입니다"라는 오류 메시지를 표시한다.
