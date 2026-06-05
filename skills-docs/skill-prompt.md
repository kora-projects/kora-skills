Iterative Kora Framework Claude Skill Development Prompt

Objective

Analyze the Kora framework documentation iteratively to create a comprehensive set
of production-ready Claude skills for the kora-developer skill package, using
AGENTS.md as the primary foundation.

Iterative Development Process

Phase 1: Skill Identification and Prioritization

Task: Analyze AGENTS.md and documentation structure to identify required Claude    
skills
1. Review AGENTS.md in the project root as the primary foundation
2. Cross-reference with agents-md/kora-docs/mkdocs/docs/en/documentation/ directory
   structure
3. Identify core documentation files and their relationships
4. Create prioritized list of Claude skills based on foundational dependencies
5. Define skill boundaries and responsibilities for the kora-developer package

Output: Ordered list of Claude skills to develop with brief descriptions for the   
kora-developer skill package

Phase 2: Iterative Claude Skill Development Cycle

For each Claude skill in priority order, execute the following cycle:

Step 1: Targeted Documentation Analysis

Task: Read only documentation relevant to current Claude skill
1. Identify specific documentation files for current Claude skill
2. Focus on examples and code samples for this skill area
3. Extract patterns, best practices, and implementation approaches
4. Note configuration requirements and constraints
5. Cross-reference with AGENTS.md for foundational principles

Step 2: Example Code Deep Dive

Task: Study relevant example projects for Claude skill creation
1. Locate example code in agents-md/kora-examples/ for current Claude skill
2. Analyze implementation patterns and structures
3. Extract reusable templates and code snippets
4. Identify common anti-patterns and solutions
5. Validate against AGENTS.md principles

Step 3: Claude Skill Specification Creation

Task: Define the Claude skill structure and content
1. Create Claude skill objectives and capabilities based on AGENTS.md foundation
2. Define prerequisites and dependencies for the Claude skill
3. Outline implementation workflows for users
4. Specify configuration patterns and requirements
5. Ensure alignment with AGENTS.md architectural principles

Step 4: Claude Skill Implementation Planning

Task: Plan the Claude skill components
1. Design automation scripts (if needed) for the Claude skill
2. Create reference documentation structure for the Claude skill
3. Develop template assets for the Claude skill
4. Define validation and testing approaches for the Claude skill
5. Maintain consistency with AGENTS.md guidelines

Step 5: Claude Skill Assembly

Task: Create the complete Claude skill package
1. Write SKILL.md with proper frontmatter, incorporating AGENTS.md principles for  
   the Claude skill
2. Create reference documentation files for the Claude skill
3. Develop automation scripts for the Claude skill
4. Prepare template assets for the Claude skill
5. Validate against AGENTS.md foundational concepts

Required Claude Skills Development Sequence for kora-developer Package

1. kora-basic (Foundational Claude Skill)

Focus Areas:
- container.md documentation
- config.md documentation
- Project setup and Gradle configuration
- Dependency injection fundamentals
- Application lifecycle
- Alignment with AGENTS.md foundational principles

2. kora-json (JSON Processing Claude Skill)

Focus Areas:
- JSON handling documentation
- Serialization/deserialization patterns
- JSON reader/writer usage
- Custom serializer implementation
- Performance considerations

3. kora-server (HTTP Server Development Claude Skill)

Focus Areas:
- http-server.md documentation
- Controller patterns and routing
- Request/response handling
- Error management

4. kora-client (Client Development Claude Skill)

Focus Areas:
- HTTP client documentation
- Client interface patterns
- Configuration and error handling

5. kora-openapi (API Contract Generation Claude Skill)

Focus Areas:
- OpenAPI integration documentation
- Code generation patterns
- Specification management

6. kora-aop (Aspect-Oriented Programming & Cross-Cutting Concerns Claude Skill)

Focus Areas:
- AOP documentation
- Custom annotation creation
- Method interception patterns
- Validation patterns and implementation
- Logging aspects and structured logging
- Resilience patterns (circuit breaker, retry, timeout)
- Scheduling mechanisms and cron expressions
- Caching strategies and implementation

7. kora-kafka (Messaging Claude Skill)

Focus Areas:
- Kafka documentation
- Producer/consumer patterns
- Event-driven architecture

8. kora-telemetry (Observability Claude Skill)

Focus Areas:
- Metrics documentation
- Tracing documentation
- Logging documentation
- Health check patterns

9. kora-database (Data Access Claude Skill)

Focus Areas:
- database-jdbc.md documentation
- Repository patterns
- Transaction management
- Entity mapping

Final Output: Complete kora-developer Skill Package

Package Structure:

kora-developer/                                           
├── SKILL.md              # Master documentation for the complete package          
├── kora-basic/           # Foundational Claude skill                              
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-json/            # JSON processing Claude skill                           
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-server/          # HTTP server development Claude skill
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-client/          # Client development Claude skill                        
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-openapi/ # API contract generation Claude skill                 
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-aop/             # AOP and cross-cutting concerns Claude skill            
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-kafka/           # Messaging Claude skill                                 
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                                                    
├── kora-telemetry/       # Observability Claude skill                             
│   ├── SKILL.md                                                                   
│   ├── scripts/                                                                   
│   ├── references/                                                                
│   └── assets/                                           
└── kora-database/        # Data access Claude skill                               
├── SKILL.md                                                                   
├── scripts/                                                                   
├── references/                                                                
└── assets/

Iteration Quality Gates

Before Moving to Next Claude Skill:

1. Documentation Completeness Check:                                               
   - All relevant documentation analyzed
   - Key patterns identified and documented                                         
   - Best practices extracted                              
   - AGENTS.md principles validated and applied
2. Example Validation:                                                             
   - Relevant examples reviewed                                                     
   - Implementation patterns confirmed                                              
   - Templates extracted                                                            
   - AGENTS.md guidelines verified
3. Claude Skill Specification Review:                                              
   - Objectives clearly defined                                                     
   - Workflows outlined                                                             
   - Dependencies mapped                                                            
   - AGENTS.md alignment confirmed
4. Consistency Verification:                                                       
   - Patterns aligned with previous Claude skills          
   - Configuration requirements consistent                                          
   - Gradle/build requirements maintained                                           
   - AGENTS.md foundational principles preserved

Claude Skill Creation Standards

For Each Claude Skill, Ensure:

1. Gradle Configuration Consistency:                                               
   - Double quotes in build.gradle files                   
   - Proper dependency declarations                                                 
   - Plugin configurations
2. Code Structure Recommendations:
   - Record usage where appropriate                                                 
   - Interface-based configuration patterns                
   - Annotation-based dependency injection
3. Development Approach Guidance:                         
   - Contract-first when applicable                                                 
   - Error handling patterns                                                        
   - Testing strategies
4. Integration Considerations:                                                     
   - Compatibility with previously created Claude skills                            
   - Shared configuration patterns                                                  
   - Common utility usage                                                           
   - AGENTS.md architectural consistency
5. Foundation Alignment:                                  
   - All Claude skills must align with AGENTS.md principles                         
   - Core concepts from AGENTS.md must be preserved                                 
   - Claude skill boundaries should reflect AGENTS.md organization

Output Format Per Claude Skill

1. Claude skill name and description
2. Prerequisites and dependencies
3. Core concepts and patterns
4. Implementation workflow
5. Configuration examples
6. Best practices and recommendations
7. Common pitfalls and solutions
8. Reference documentation links
9. Template code samples
10. Validation criteria
11. AGENTS.md foundation alignment statement

Final Validation for Complete kora-developer Package

1. Package Cohesion Check:                                                         
   - All Claude skills integrate seamlessly                
   - No conflicting patterns or approaches                                          
   - Consistent terminology and conventions
   - Shared utility libraries properly referenced
2. Foundation Integrity:                                                           
   - Complete alignment with AGENTS.md principles                                   
   - Preservation of core architectural concepts                                    
   - Consistent application of Kora framework patterns
3. Production Readiness:                                                           
   - All Claude skills tested and validated                                         
   - Documentation complete and accurate                                            
   - Examples functional and representative                                         
   - Templates ready for immediate use
4. User Experience:                                       
   - Clear learning progression across Claude skills                                
   - Appropriate difficulty ramp                           
   - Comprehensive coverage of Kora capabilities                                    
   - Practical, real-world applicability