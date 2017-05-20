<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet xmlns:h="http://www.w3.org/1999/xhtml"
                xmlns:xml="http://www.w3.org/XML/1998/namespace"
                xmlns:xhtmlim="http://jabber.org/protocol/xhtml-im"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                version="1.0">
  <!-- This XSL is in alpha stage. Do not use. -->

  <xsl:output method="xml" indent="no" standalone="yes" encoding="utf-8" />

  <!-- text is allowed -->
  <xsl:template match="text()">
    <xsl:copy/>
  </xsl:template>

  <!-- attributes are passed; the selection of attributes happens in the
       individual elements templates -->
  <xsl:template match="@*">
    <xsl:copy/>
  </xsl:template>

  <xsl:strip-space elements="*" />

  <!-- unknown elements get stripped, replaced by their children (including text
       nodes, excluding attributes)-->
  <xsl:template match="node()">
    <!-- we are deliberately excluding attributes here -->
    <xsl:apply-templates select="node()" />
  </xsl:template>

  <!-- elements which allow the style attribute -->
  <xsl:template match="h:blockquote | h:cite | h:li | h:ol | h:p | h:span | h:ul">
    <xsl:copy>
      <xsl:apply-templates select="@style" />
      <xsl:apply-templates select="node()" />
    </xsl:copy>
  </xsl:template>

  <!-- elements which allow no attributes -->
  <xsl:template match="h:br | h:em | h:strong">
    <xsl:copy>
      <xsl:apply-templates select="node()" />
    </xsl:copy>
  </xsl:template>

  <!-- the a element allows style, href and type -->
  <xsl:template match="h:a">
    <xsl:copy>
      <xsl:apply-templates select="@style" />
      <xsl:apply-templates select="@href" />
      <xsl:apply-templates select="@type" />
      <xsl:apply-templates select="node()" />
    </xsl:copy>
  </xsl:template>

  <!-- the img element allows alt, height, src, style and width -->
  <xsl:template match="h:img">
    <xsl:copy>
      <xsl:apply-templates select="@alt" />
      <xsl:apply-templates select="@height" />
      <xsl:apply-templates select="@src" />
      <xsl:apply-templates select="@style" />
      <xsl:apply-templates select="@width" />
      <xsl:apply-templates select="node()" />
    </xsl:copy>
  </xsl:template>

  <!-- any top-level element which is not h:body or xhtmlim:html does not
       produce output -->
  <xsl:template match="/*">
    <xsl:message terminate="yes">
      <xsl:text>ERROR: The top-level element must be either</xsl:text>
      <xsl:text> {http://jabber.org/protocol/xhtml-im}html or</xsl:text>
      <xsl:text> {http://www.w3.org/1999/xhtml}body: Found {</xsl:text>
      <xsl:value-of select="namespace-uri(.)" />
      <xsl:text>}</xsl:text>
      <xsl:value-of select="local-name(.)" />
      <xsl:text> instead.</xsl:text>
    </xsl:message>
  </xsl:template>

  <!-- the body allows style and xml:lang; we allow body only on the top level
       or in a top-level xhtmlim:html element. -->
  <xsl:template match="/xhtmlim:html/h:body | /h:body">
    <xsl:copy>
      <xsl:apply-templates select="@style" />
      <xsl:apply-templates select="@xml:lang" />
      <xsl:apply-templates select="node()" />
    </xsl:copy>
  </xsl:template>

  <!-- we allow xhtmlim:html only at the toplevel -->
  <xsl:template match="/xhtmlim:html">
    <xsl:copy>
      <xsl:apply-templates select="h:body" />
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
