JUNIT_DEPENDENCY_XML = """
    <dependency>
        <groupId>junit</groupId>
        <artifactId>junit</artifactId>
        <version>4.13.2</version>
        <scope>test</scope>
    </dependency>
"""


MOCKITO_DEPENDENCY_XML = """
    <dependency>
        <groupId>org.mockito</groupId>
        <artifactId>mockito-core</artifactId>
        <version>4.11.0</version>
        <scope>test</scope>
    </dependency>
"""


SUREFIRE_PLUGIN_XML = """
    <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.2.5</version>
        <configuration>
            <argLine>@{argLine}</argLine>
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


FIXED_DEPENDENCIES = (
    JUNIT_DEPENDENCY_XML,
    MOCKITO_DEPENDENCY_XML,
)


FIXED_PLUGINS = (
    SUREFIRE_PLUGIN_XML,
)
