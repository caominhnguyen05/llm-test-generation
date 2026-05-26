JUNIT_DEPENDENCY_XML = """
    <dependency>
        <!-- This element was inserted by download.py -->
        <groupId>junit</groupId>
        <artifactId>junit</artifactId>
        <version>4.13.2</version>
        <scope>test</scope>
    </dependency>
"""


MOCKITO_DEPENDENCY_XML = """
    <dependency>
        <!-- This element was inserted by download.py -->
        <groupId>org.mockito</groupId>
        <artifactId>mockito-core</artifactId>
        <version>4.11.0</version>
        <scope>test</scope>
    </dependency>
"""


SUREFIRE_PLUGIN_XML = """
    <plugin>
        <!-- This element was inserted by download.py -->
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.2.5</version>
        <configuration>
            <argLine>@{jacoco.argLine}</argLine>
            <includes>
                <include>**/*Test.java</include>
            </includes>
        </configuration>
        <dependencies>
            <dependency>
                <groupId>org.apache.maven.surefire</groupId>
                <artifactId>surefire-junit4</artifactId>
                <version>3.2.5</version>
            </dependency>
        </dependencies>
    </plugin>
"""


JACOCO_PLUGIN_XML = """
    <plugin>
        <!-- This element was inserted by download.py -->
        <groupId>org.jacoco</groupId>
        <artifactId>jacoco-maven-plugin</artifactId>
        <version>0.8.12</version>
        <configuration>
            <propertyName>jacoco.argLine</propertyName>
            <excludes>
                <exclude>META-INF/versions/**</exclude>
            </excludes>
        </configuration>
        <executions>
            <execution>
                <id>prepare-agent</id>
                <goals>
                    <goal>prepare-agent</goal>
                </goals>
            </execution>
            <execution>
                <id>report</id>
                <phase>verify</phase>
                <goals>
                    <goal>report</goal>
                </goals>
            </execution>
        </executions>
    </plugin>
"""


FIXED_DEPENDENCIES = (
    JUNIT_DEPENDENCY_XML,
    MOCKITO_DEPENDENCY_XML,
)


FIXED_PLUGINS = (
    SUREFIRE_PLUGIN_XML,
    JACOCO_PLUGIN_XML,
)
