<?xml version="1.0" ?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="text" encoding="utf-8" />

  <xsl:template match="root">
    <xsl:text>class Features(Enum):
    """</xsl:text>
    <xsl:for-each select="var">
      <xsl:text>
    .. attribute:: </xsl:text>
      <xsl:value-of select="translate(substring-after(name, '#'), 'abcdefghijklmnopqrstuvwxyz-', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_')" />
      <xsl:text>
       :annotation: = "</xsl:text>
      <xsl:value-of select="name" />
      <xsl:text>"

       </xsl:text>
      <xsl:value-of select="normalize-space(desc)"/>
      <xsl:text>
</xsl:text>
    </xsl:for-each>
    <xsl:text>
    """
    </xsl:text>
    <xsl:for-each select="var">
      <xsl:text>
    </xsl:text>
      <xsl:value-of select="translate(substring-after(name, '#'), 'abcdefghijklmnopqrstuvwxyz-', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_')" />
      <xsl:text> = \
        "</xsl:text>
      <xsl:value-of select="name" />
      <xsl:text>"</xsl:text>
    </xsl:for-each>
    <xsl:text>
</xsl:text>
  </xsl:template>
</xsl:stylesheet>
